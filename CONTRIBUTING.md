# Contributing to Fellow Stagg EKG Pro Integration

Thank you for considering contributing to this project!

## How to Contribute

### Reporting Bugs

1. Check if the issue already exists in [GitHub Issues](https://github.com/cermakjn/ha-fellow-stagg-ekg-pro/issues)
2. If not, create a new issue with:
   - A clear description of the problem
   - Steps to reproduce
   - Your Home Assistant version
   - Relevant logs (Settings → System → Logs)

### Suggesting Features

Open an issue with the `enhancement` label describing your idea.

### Pull Requests

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Test your changes with a real Fellow Stagg EKG Pro kettle
5. Commit your changes (`git commit -m 'Add amazing feature'`)
6. Push to the branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

### Development Setup

1. Clone the repository
2. Copy `custom_components/fellow_stagg_ekg_pro` to your Home Assistant's `custom_components` directory
3. Restart Home Assistant
4. Make changes and restart to test

### Local Validation

Before submitting a PR, you can run the Home Assistant hassfest validation locally using Docker:

```bash
cd /path/to/ha-fellow-stagg-ekg-pro
docker run --rm -v "$(pwd)/custom_components:/github/workspace/custom_components" ghcr.io/home-assistant/hassfest:latest
```

This validates:
- Manifest file structure
- Dependencies
- Services definition
- Config flow
- And other Home Assistant integration requirements

A successful run will show `Invalid integrations: 0`.

### Code Style

- Follow PEP 8 guidelines
- Use type hints where possible
- Add docstrings to functions and classes
- Keep code compatible with Home Assistant 2024.1.0+

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
