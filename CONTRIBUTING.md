# Contributing to NestNetController

Thank you for considering contributing to NestNetController!

## Getting Started

1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/NestNetController.git`
3. Create a branch: `git checkout -b feature/your-feature-name`
4. Make your changes
5. Test in dry-run mode first
6. Commit with clear messages
7. Push to your fork
8. Open a Pull Request

## Development Setup

```bash
# Copy environment file
cp .env.example .env

# Edit .env with your settings
# Set DRY_RUN=true for development

# Start the stack
docker-compose up --build
```

## Testing

Always test changes in dry-run mode first:

```bash
DRY_RUN=true docker-compose up
```

Verify:
- Backend API responds at http://localhost:8002
- Frontend loads at http://localhost:3002
- No actual iptables rules are modified

## Code Style

- **Python**: Follow PEP 8
- **JavaScript**: Use ES6+ features
- **Comments**: Explain why, not what

## Pull Request Guidelines

- Keep PRs focused on a single feature or fix
- Update README.md if adding features
- Include screenshots for UI changes
- Test thoroughly before submitting
- Write clear commit messages

## Reporting Bugs

Use GitHub Issues and include:
- Steps to reproduce
- Expected vs actual behavior
- Your environment (OS, Docker version)
- Relevant logs

## Feature Requests

Open an issue with:
- Clear description of the feature
- Use case / why it's needed
- Proposed implementation (optional)

## Questions?

Open a discussion or issue on GitHub.

Thank you for helping make NestNetController better!
