## Project Best Practices

- Always keep code to a minium. We are aiming to ship this work in as little code as feasibly possible.
- Use environment variables for all configuration (model names, thresholds, intervals). Never hardcode.
- Fail fast on startup: validate GPU, models, webcam access before entering main loop.
- Log sparingly: only state transitions, errors, and user actions. Avoid verbose debug logs in production.
- Favor composition over abstraction: small focused functions over complex class hierarchies.
- Use type hints for all function signatures to catch errors early.
- Handle model loading errors gracefully: retry once, fallback to lighter model, then fail with clear message.
- Keep Docker images minimal: use slim Python base images, multi-stage builds where possible.
- Cache aggressively: models, embeddings, calibration comparisons. Optimize for inference speed.
- Test service isolation: each service should run/test independently before integration.
- Use comments sparingly and only to clarify services or more complex design decisions.
