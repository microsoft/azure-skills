# Large File Uploads

The standard `client.files.create()` silently fails on JSONL files >~150MB (Azure returns 500 during job execution). Use the chunked Uploads API:

```python
upload = client.uploads.create(filename="data.jsonl", purpose="fine-tune", bytes=file_size, mime_type="application/jsonl")
part_ids = []
with open(filepath, "rb") as f:
    while chunk := f.read(64 * 1024 * 1024):  # 64MB chunks
        part = client.uploads.parts.create(upload_id=upload.id, data=chunk)
        part_ids.append(part.id)
completed = client.uploads.complete(upload_id=upload.id, part_ids=part_ids)
file_id = completed.file.id
```

**Important:** Requires `openai.AzureOpenAI()` client, NOT `openai.OpenAI()` with `/v1/` URL. The project endpoint returns 404 for upload operations.

| File Size | Method |
|-----------|--------|
| < 100MB | Standard `files.create()` |
| 100MB–5GB | Chunked Uploads API |
| > 5GB | Split dataset |
