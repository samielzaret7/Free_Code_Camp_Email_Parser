/**
 * FreeCodeCamp Email Ingest — Google Apps Script
 *
 * Replaces the honcho-based emlScript.py pipeline.
 * Flow: Gmail → Groq LLM → Supabase (courses_staging)
 *
 * SETUP:
 *   1. Create a new Google Apps Script project at script.google.com
 *   2. Paste this file as Code.gs
 *   3. Go to Project Settings > Script Properties and add:
 *        SUPABASE_URL              — e.g. https://xxxxx.supabase.co
 *        SUPABASE_SERVICE_ROLE_KEY — your JWT service_role key (NOT sb_secret_)
 *        GROQ_API_KEY              — your Groq API key
 *   4. Go to Triggers (clock icon) > Add Trigger:
 *        Function: main
 *        Event source: Time-driven
 *        Type: Minutes timer / Hour timer (your choice)
 *   5. On first run, authorize Gmail access when prompted.
 */


// ---------------------------------------------------------------------------
// Configuration helpers
// ---------------------------------------------------------------------------

function getConfig_(key) {
  var val = PropertiesService.getScriptProperties().getProperty(key);
  if (!val) throw new Error("Missing Script Property: " + key);
  return val;
}


// ---------------------------------------------------------------------------
// Allowed categories (mirror of api/categories.py)
// ---------------------------------------------------------------------------

var ALLOWED_CATEGORIES = [
  // Core programming
  "Python", "JavaScript", "C#", "Programming Fundamentals",
  "Software Development", "Software Engineering", "Computer Science",
  "Operating Systems", "Linux",
  // Web & Mobile
  "Web Development", "Frontend Development", "Backend Development",
  "Full Stack Development", "React", "Flutter", "Mobile Development",
  // Cloud & Infrastructure
  "Cloud Computing", "AWS", "Networking", "Security", "Cybersecurity",
  // AI, ML & Data
  "Artificial Intelligence", "Machine Learning", "Deep Learning",
  "Large Language Models", "Data Science", "Data Analysis",
  "Data Engineering", "Databases", "GPU Computing",
  // Embedded & Hardware
  "Embedded Systems", "IoT", "Hardware", "Robotics",
  // Math & Theory
  "Mathematics", "Statistics",
  // Career & Soft Skills
  "Career Development", "Emerging Technologies",
  // Miscellaneous
  "Cloud & DevOps"
];


// ---------------------------------------------------------------------------
// Gmail: fetch unread emails from quincy@freecodecamp.org
// ---------------------------------------------------------------------------

function fetchUnreadEmails_() {
  var threads = GmailApp.search("from:quincy@freecodecamp.org is:unread", 0, 20);
  var results = [];

  for (var t = 0; t < threads.length; t++) {
    var messages = threads[t].getMessages();
    for (var m = 0; m < messages.length; m++) {
      var msg = messages[m];
      if (msg.isUnread()) {
        results.push({
          messageId: msg.getId(),
          from: msg.getFrom(),
          subject: msg.getSubject(),
          body: msg.getBody()   // returns HTML body
        });
      }
    }
  }

  Logger.log("Fetched " + results.length + " unread message(s)");
  return results;
}


// ---------------------------------------------------------------------------
// Groq: extract courses from email HTML via LLM
// ---------------------------------------------------------------------------

function askGroq_(model, html) {
  var GROQ_URL = "https://api.groq.com/openai/v1/chat/completions";
  var GROQ_API_KEY = getConfig_("GROQ_API_KEY");

  var allowedList = "\n- " + ALLOWED_CATEGORIES.join("\n- ");

  var prompt =
    "You are extracting FreeCodeCamp courses from an EMAIL HTML.\n" +
    "Return ONLY valid JSON in this schema:\n\n" +
    "{\n" +
    '  "items": [\n' +
    "    {\n" +
    '      "name": "string (required)",\n' +
    '      "link": "string|null",\n' +
    '      "time": "string|null",\n' +
    '      "description": "string|null",\n' +
    '      "categories": ["string"],\n' +
    '      "category_confidence": 0.0,\n' +
    '      "suggested_new_category": "string|null",\n' +
    '      "date_added": "YYYY-MM-DD|null"\n' +
    "    }\n" +
    "  ]\n" +
    "}\n\n" +
    "Rules:\n" +
    "- Choose up to 3 categories from the allowed list below that best describe each course.\n" +
    "- If no categories apply, set categories=[] and fill suggested_new_category.\n" +
    "- Do NOT invent category names.\n" +
    "- Prefer more specific categories (e.g., 'React' instead of 'Web Development').\n" +
    "- Clean titles and prefer canonical course links.\n\n" +
    "Allowed categories:" + allowedList + "\n\n" +
    "EMAIL HTML:\n<<<HTML\n" + html + "\nHTML>>>";

  var payload = {
    model: model,
    temperature: 0,
    response_format: { type: "json_object" },
    messages: [{ role: "user", content: prompt }]
  };

  var options = {
    method: "post",
    contentType: "application/json",
    headers: { "Authorization": "Bearer " + GROQ_API_KEY },
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  };

  // Retry with exponential backoff on 429
  for (var attempt = 0; attempt < 6; attempt++) {
    var response = UrlFetchApp.fetch(GROQ_URL, options);
    var code = response.getResponseCode();

    if (code === 200) {
      var content = JSON.parse(response.getContentText());
      return JSON.parse(content.choices[0].message.content);
    }

    if (code === 429) {
      var wait = Math.pow(2, attempt);
      Logger.log("[groq] 429 rate-limited on " + model + ". Sleeping " + wait + "s...");
      Utilities.sleep(wait * 1000);
      continue;
    }

    throw new Error("Groq " + model + " returned " + code + ": " + response.getContentText());
  }

  // All retries exhausted
  Logger.log("[groq] All retries exhausted for " + model);
  return { items: [] };
}


function extractItems_(html) {
  var PRIMARY_MODEL = "llama-3.1-8b-instant";
  var FALLBACK_MODEL = "gemma2-9b-it";

  try {
    return askGroq_(PRIMARY_MODEL, html);
  } catch (e) {
    Logger.log("Primary model '" + PRIMARY_MODEL + "' failed: " + e.message +
               ". Falling back to '" + FALLBACK_MODEL + "'");
    try {
      return askGroq_(FALLBACK_MODEL, html);
    } catch (e2) {
      Logger.log("Fallback model '" + FALLBACK_MODEL + "' also failed: " + e2.message);
      return { items: [] };
    }
  }
}


// ---------------------------------------------------------------------------
// Supabase: insert rows into courses_staging
// ---------------------------------------------------------------------------

function insertStaging_(rows) {
  if (!rows || rows.length === 0) return 0;

  var SUPABASE_URL = getConfig_("SUPABASE_URL").replace(/\/+$/, "");
  var SUPABASE_KEY = getConfig_("SUPABASE_SERVICE_ROLE_KEY");
  var TABLE_STAGING = "courses_staging";

  var url = SUPABASE_URL + "/rest/v1/" + TABLE_STAGING;

  var options = {
    method: "post",
    contentType: "application/json",
    headers: {
      "apikey": SUPABASE_KEY,
      "Authorization": "Bearer " + SUPABASE_KEY,
      "Prefer": "return=minimal,resolution=ignore-duplicates"
    },
    payload: JSON.stringify(rows),
    muteHttpExceptions: true
  };

  var response = UrlFetchApp.fetch(url, options);
  var code = response.getResponseCode();

  if (code >= 200 && code < 300) {
    Logger.log("Inserted " + rows.length + " row(s) into " + TABLE_STAGING);
    return rows.length;
  }

  var body = response.getContentText();

  // Treat duplicate constraint errors as idempotent success
  if (body.indexOf("23505") !== -1 || body.indexOf("duplicate key") !== -1) {
    Logger.log("Duplicate detected (treating as success). status=" + code);
    return rows.length;
  }

  throw new Error("Supabase insert failed (" + code + "): " + body);
}


// ---------------------------------------------------------------------------
// Main orchestrator
// ---------------------------------------------------------------------------

function main() {
  Logger.log("=== FreeCodeCamp Ingest run started ===");

  var emails = fetchUnreadEmails_();
  if (emails.length === 0) {
    Logger.log("No unread emails. Done.");
    return;
  }

  var today = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), "yyyy-MM-dd");
  var totalStaged = 0;

  for (var i = 0; i < emails.length; i++) {
    var email = emails[i];
    Logger.log("Processing email: " + email.subject);

    var parsed = extractItems_(email.body);
    var items = parsed.items || [];

    if (items.length === 0) {
      Logger.log("  No items extracted. Skipping.");
      // Still mark as read so we don't re-process empty emails
      markAsRead_(email.messageId);
      continue;
    }

    // Build rows (mirrors api/main.py logic)
    var rows = [];
    for (var j = 0; j < items.length; j++) {
      var it = items[j];
      var cats = (it.categories || []).filter(function (c) {
        return ALLOWED_CATEGORIES.indexOf(c) !== -1;
      });
      var best = cats.length > 0 ? cats[0] : "Uncategorized";

      rows.push({
        source_sender: email.from,
        source_subject: email.subject,
        name: it.name,
        link: it.link || null,
        time: it.time || null,
        description: it.description || null,
        categories: cats.length > 0 ? cats : null,
        category: best,
        category_confidence: it.category_confidence || null,
        suggested_new_category: it.suggested_new_category || null,
        date_added: today
      });
    }

    try {
      var staged = insertStaging_(rows);
      totalStaged += staged;
      // A2 semantics: only mark as read after successful insert
      markAsRead_(email.messageId);
      Logger.log("  Staged " + staged + " item(s). Email marked as read.");
    } catch (e) {
      Logger.log("  ERROR inserting: " + e.message + ". Email left unread for retry.");
    }

    // Rate-limit courtesy delay between emails
    if (i < emails.length - 1) {
      Utilities.sleep(3000);
    }
  }

  Logger.log("=== Run complete. Total staged: " + totalStaged + " ===");
}


// ---------------------------------------------------------------------------
// Gmail: mark a single message as read
// ---------------------------------------------------------------------------

function markAsRead_(messageId) {
  try {
    var msg = GmailApp.getMessageById(messageId);
    if (msg) msg.markRead();
  } catch (e) {
    Logger.log("Failed to mark message " + messageId + " as read: " + e.message);
  }
}
