# Contributing to SnPViewer

Thank you for your interest in contributing to SnPViewer! This document provides guidelines and information for contributors.

## 🚀 Getting Started

### Development Setup

1. **Fork and Clone**

   ```bash
   git clone https://github.com/yourusername/SnPViewer.git
   cd SnPViewer
   ```

2. **Environment Setup**

   ```bash
   # Using uv (recommended)
   uv sync

   # Or using pip
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Verify Installation**
   ```bash
   uv run pytest  # Run tests
   uv run python -m frontend.app  # Run application
   ```

## 🧪 Development Workflow

### Code Quality Standards

We maintain high code quality standards:

```bash
# Linting and formatting
uv run ruff check .    # Check for issues
uv run ruff format .   # Auto-format code

# Testing
uv run pytest                    # Run all tests
uv run pytest --cov=backend     # With coverage
uv run pytest -v tests/specific_test.py  # Specific tests
```

### Code Style Guidelines

- **Follow PEP 8**: Use ruff for automated formatting
- **Type Hints**: All functions should have type annotations
- **Docstrings**: Use Google-style docstrings for all public functions
- **Import Order**: Follow isort conventions (handled by ruff)

Example function:

```python
def parse_frequency(value: str) -> float:
    """Parse frequency string with suffix support.

    Args:
        value: Frequency string (e.g., "2.4G", "1e9", "900M")

    Returns:
        Frequency value in Hz

    Raises:
        ValueError: If the frequency string is invalid
    """
    # Implementation here
```

## 🏗️ Architecture Overview

### Frontend Structure

- **widgets/**: Custom Qt widgets and UI components
- **dialogs/**: Property dialogs and user interactions
- **services/**: Background services and utilities
- **app.py**: Main application window and coordination

### Backend Structure

- **models/**: Data structures (Dataset, Chart, Project, etc.)
- **parsing/**: Touchstone file parsing and conversion
- **services/**: Business logic and data processing

### Key Design Principles

- **Separation of Concerns**: UI logic separate from business logic
- **Signal-Slot Architecture**: Qt-based event handling
- **Model-View Pattern**: Clean data and presentation separation
- **Type Safety**: Comprehensive type hints throughout

## 🎯 Contribution Areas

### High-Priority Areas

1. **Export Features**: Chart export to PNG, PDF, SVG
2. **Performance**: Optimization for large datasets
3. **Testing**: Increase test coverage
4. **Documentation**: User guides and API documentation
5. **Accessibility**: Screen reader and keyboard support

### Feature Categories

#### 🔧 **Core Features**

- Touchstone parsing improvements
- New chart types and visualizations
- Mathematical analysis tools
- Data export capabilities

#### 🎨 **UI/UX Improvements**

- Visual design enhancements
- User experience improvements
- Accessibility features
- Internationalization

#### ⚡ **Performance & Quality**

- Code optimization
- Memory usage improvements
- Test coverage expansion
- Bug fixes and stability

## 📝 Pull Request Process

### Before Submitting

1. **Create Feature Branch**

   ```bash
   git checkout -b feature/your-feature-name
   git checkout -b bugfix/issue-description
   ```

2. **Write Tests**

   - Add tests for new functionality
   - Ensure existing tests still pass
   - Aim for high test coverage

3. **Update Documentation**

   - Update docstrings for new/modified functions
   - Update README.md if needed
   - Add inline comments for complex logic

4. **Code Quality Check**
   ```bash
   uv run ruff check .    # No linting errors
   uv run ruff format .   # Consistent formatting
   uv run pytest         # All tests pass
   ```

### Pull Request Guidelines

1. **Title**: Clear, descriptive title

   - ✅ "Add SVG export functionality to charts"
   - ❌ "Update stuff"

2. **Description**: Include:

   - What changes were made
   - Why the changes were necessary
   - How to test the changes
   - Screenshots for UI changes

3. **Commits**:

   - Use clear, descriptive commit messages
   - Keep commits focused and atomic
   - Follow conventional commit format if possible

4. **Testing**:
   - All new code should have tests
   - All existing tests must pass
   - Manual testing instructions if applicable

### Example Pull Request Template

```markdown
## Description

Brief description of the changes made.

## Type of Change

- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## Testing

- [ ] Unit tests added/updated
- [ ] Manual testing completed
- [ ] All tests pass

## Screenshots (if applicable)

Add screenshots to help explain your changes.

## Checklist

- [ ] Code follows the project's style guidelines
- [ ] Self-review of code completed
- [ ] Code is commented, particularly in hard-to-understand areas
- [ ] Documentation updated as needed
- [ ] No new warnings introduced
```

## 🐛 Bug Reports

### Before Reporting

1. Check existing issues to avoid duplicates
2. Test with the latest version
3. Gather system information

### Bug Report Template

```markdown
**Describe the Bug**
A clear description of what the bug is.

**To Reproduce**
Steps to reproduce the behavior:

1. Go to '...'
2. Click on '....'
3. See error

**Expected Behavior**
What you expected to happen.

**Screenshots**
If applicable, add screenshots.

**Environment:**

- OS: [e.g. Windows 10, macOS 12.6, Ubuntu 22.04]
- Python Version: [e.g. 3.11.5]
- SnPViewer Version: [e.g. 1.2.3]

**Additional Context**
Any other context about the problem.
```

## 💡 Feature Requests

### Feature Request Template

```markdown
**Is your feature request related to a problem?**
A clear description of what the problem is.

**Describe the solution you'd like**
A clear description of what you want to happen.

**Describe alternatives you've considered**
Other solutions or features you've considered.

**Additional context**
Any other context or screenshots about the feature request.
```

## 🎓 Learning Resources

### Qt/PySide6 Development

- [PySide6 Documentation](https://doc.qt.io/qtforpython/)
- [Qt Documentation](https://doc.qt.io/)
- [PyQtGraph Documentation](https://pyqtgraph.readthedocs.io/)

### RF Engineering

- [Touchstone File Format](https://en.wikipedia.org/wiki/Touchstone_file)
- [S-Parameters](https://en.wikipedia.org/wiki/Scattering_parameters)
- [Smith Chart](https://en.wikipedia.org/wiki/Smith_chart)

### Python Development

- [PEP 8 Style Guide](https://pep8.org/)
- [Type Hints](https://docs.python.org/3/library/typing.html)
- [pytest Documentation](https://docs.pytest.org/)

## 🤝 Community

### Communication Channels

- **GitHub Issues**: For bug reports and feature requests
- **GitHub Discussions**: For questions and general discussion
- **Pull Requests**: For code contributions

### Code of Conduct

We are committed to providing a welcoming and inclusive environment for all contributors. Please be:

- **Respectful**: Treat all community members with respect
- **Constructive**: Provide helpful feedback and suggestions
- **Collaborative**: Work together towards common goals
- **Patient**: Help newcomers learn and contribute

## 🏆 Recognition

Contributors are recognized in several ways:

- Listed in the README.md contributors section
- Mentioned in release notes for significant contributions
- GitHub contributor statistics and graphs
- Special recognition for major features or improvements

## ❓ Questions?

If you have questions about contributing:

1. Check existing GitHub Discussions
2. Open a new Discussion for general questions
3. Contact maintainers for specific guidance

Thank you for contributing to SnPViewer! 🚀
