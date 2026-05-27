# Vision Fine-Tuning

Fine-tune models with image data to customize visual understanding. Uses the same chat-completions JSONL format as text SFT, but with image content blocks in user messages.

## Supported Models

| Model | Version |
|-------|---------|
| gpt-4o | 2024-08-06 |
| gpt-4.1 | 2025-04-14 |

## Image Requirements

| Constraint | Limit |
|-----------|-------|
| Max examples with images per training file | 50,000 |
| Max images per example | 64 |
| Max image file size | 10 MB |
| Supported formats | JPEG, PNG, WEBP |
| Color mode | RGB or RGBA |
| Min examples | 10 |

**Important**: Images can only appear in `user` messages, never in `assistant` responses.

## Data Format

Each training example follows the standard SFT `messages` format. Images are included as `image_url` content blocks within user messages.

```jsonl
{"messages": [{"role": "system", "content": "You are a helpful AI assistant that describes images."}, {"role": "user", "content": [{"type": "text", "text": "Describe this image."}, {"type": "image_url", "image_url": {"url": "https://example.com/photo.png", "detail": "high"}}]}, {"role": "assistant", "content": "The image shows a cityscape with tall buildings against a blue sky."}]}
```

### Image Sources

Images can be provided in two ways:

**1. Public URL:**
```json
{"type": "image_url", "image_url": {"url": "https://example.com/image.png"}}
```

**2. Base64 data URI:**
```json
{"type": "image_url", "image_url": {"url": "data:image/png;base64,iVBORw0KGgo..."}}
```

### Detail Control

The `detail` parameter controls image processing fidelity and cost:

| Value | Behavior | Cost |
|-------|----------|------|
| `low` | Downscales to 512×512 pixels | Lower |
| `high` | Full resolution processing | Higher |
| `auto` | Model decides based on image size | Default |

```json
{"type": "image_url", "image_url": {"url": "https://example.com/image.png", "detail": "low"}}
```

Use `low` for tasks where fine visual detail doesn't matter (classification, general description). Use `high` for tasks needing precise detail (OCR, diagram reading, defect detection).

## Content Moderation

Images are screened before training. The following are **automatically excluded**:

- Images containing **people or faces** (face detection only — no identification)
- **CAPTCHAs**
- Content violating Azure usage policies

This screening may add latency to file upload validation.

## Best Practices

- **Diverse examples**: Vary image content, angles, lighting, and resolution
- **Consistent annotations**: Keep assistant response style and detail level uniform
- **Start with `detail: low`**: Cheaper and faster — upgrade to `high` only if results need it
- **Check for excluded images**: After upload, verify the training count matches expectations — some images may be silently skipped due to content moderation
- **Mixed text+image**: You can include both text-only and image examples in the same training file

## Training Workflow

Vision fine-tuning follows the exact same workflow as text SFT:

1. Prepare JSONL with image content blocks
2. Upload training file (validation may take longer due to image screening)
3. Create fine-tuning job with a supported vision model
4. Monitor and evaluate as usual

```python
# Upload (image validation may take longer)
train_file = client.files.create(purpose="fine-tune", file=open("vision_train.jsonl", "rb"))
client.files.wait_for_processing(train_file.id)

# Submit — same as text SFT
job = client.fine_tuning.jobs.create(
    model="gpt-4.1-2025-04-14",
    training_file=train_file.id,
    validation_file=val_file.id,
    method={"type": "supervised"}
)
```

## Troubleshooting

| Issue | Resolution |
|-------|-----------|
| Images skipped silently | Check for people/faces, oversized files, unsupported formats |
| URL not accessible | Ensure URLs are publicly accessible, or use base64 data URIs |
| Exceeds 10 MB | Resize or compress the image |
| Wrong color mode | Convert to RGB or RGBA |
| Low quality results | Try `detail: high`, add more diverse examples, increase dataset size |

## Reference

- [Official docs](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/fine-tuning-vision)
