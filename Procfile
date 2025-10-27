api: uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
ingest: python -c "import emlScript, asyncio; asyncio.run(emlScript.main())"
ui: streamlit run ui/app.py --server.port 8501