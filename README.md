# SnPViewer

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![PySide6](https://img.shields.io/badge/PySide6-GUI-green.svg)](https://doc.qt.io/qtforpython/)
[![PyQtGraph](https://img.shields.io/badge/PyQtGraph-Plotting-orange.svg)](https://pyqtgraph.readthedocs.io/)
[![AI Assisted](https://img.shields.io/badge/AI%20Assisted-GitHub%20Copilot-purple.svg)](https://github.com/features/copilot)

A professional RF Touchstone (.sNp) parameter viewer with advanced visualization and analysis capabilities.

## ✨ Features

### 📊 **Chart Types & Visualization**

- **Magnitude & Phase Plots**: Standard S-parameter visualization with dB/linear scaling
- **Smith Charts**: Interactive Smith chart visualization for reflection coefficients
- **Group Delay Analysis**: Time-domain analysis capabilities
- **Multi-trace Support**: Compare multiple parameters on the same chart
- **Interactive Markers**: Point-and-click measurement markers with readouts

### 🎯 **Advanced Limit Lines System**

- **5 Limit Line Types**: Horizontal, Vertical, Point-based, Horizontal Range, Vertical Range
- **Smart Input Parsing**: Supports scientific notation (1e9), engineering suffixes (1G, 2.4GHz)
- **Custom Styling**: Color, line style, width, and labeling options
- **Range Validation**: Input validation with helpful error messages
- **Project Persistence**: All limit lines saved with projects

### 🎨 **Professional Styling & Customization**

- **Trace Properties**: Customize color, line style, and width for each trace
- **Font Styling**: Complete control over title, axis labels, tick labels, and legend fonts/colors
- **Plot Area Properties**: Excel-like control over backgrounds, borders, and grid appearance
- **Border Control**: Standard (left+bottom), full (all sides), or no border options
- **Project-Based Settings**: All customizations saved and restored with projects

### 💾 **Project Management**

- **Complete Project System**: Save/load entire analysis sessions
- **Unsaved Changes Protection**: Never lose work with comprehensive modification tracking
- **Dataset Management**: Organize and manage multiple Touchstone files
- **Auto-save**: Background protection against data loss

### 🔧 **File Format Support**

- **Touchstone v1/v2**: Full support for industry-standard formats
- **Multi-port Networks**: Support for 1-port to 99-port networks (.s1p to .s99p)
- **Custom Parser**: High-performance native parser with NumPy integration
- **Batch Loading**: Load entire folders of measurement files

## 🚀 Quick Start

### Prerequisites

- Python 3.11 or higher
- [uv](https://docs.astral.sh/uv/) package manager (recommended)

### Installation & Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/SnPViewer.git
cd SnPViewer

# Create and sync environment using uv
uv sync

# Run the application
uv run python -m frontend.app
```

### Alternative Installation (pip)

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the application
python -m frontend.app
```

## 📖 Usage Guide

### Basic Workflow

1. **Create New Project**: `File → New Project` or `Ctrl+N`
2. **Load Data**: `File → Open Files...` or drag-and-drop Touchstone files
3. **Create Charts**: Right-click on datasets → `Create Chart...`
4. **Add Limit Lines**: Right-click on charts → `Limit Lines → Add Limit Line...`
5. **Customize Appearance**: Right-click → `Trace Properties`, `Font Styling`, `Plot Area Properties`
6. **Save Project**: `File → Save Project` or `Ctrl+S`

### Advanced Features

#### Limit Lines

- **Quick Access**: Right-click chart → `Limit Lines` → Choose type
- **Flexible Input**: Enter `2.4G`, `2.4e9`, or `2400000000` - all equivalent
- **Range Limits**: Define pass/fail regions with filled areas
- **Point-based Limits**: Create complex limit shapes with coordinate pairs

#### Styling System

- **Trace Properties**: Double-click traces or right-click → `Trace Properties`
- **Font Styling**: Right-click → `Font Styling...` for comprehensive typography control
- **Plot Area**: Right-click → `Plot Area Properties...` for Excel-like formatting options

#### Project Management

- **Auto-protection**: Application warns before losing unsaved changes
- **Complete State**: Projects save all traces, limits, styling, and layout
- **Recent Files**: Quick access to recently used projects and data files

## 🏗️ Architecture

### Technology Stack

- **Frontend**: PySide6 (Qt for Python) - Modern, native GUI framework
- **Plotting**: PyQtGraph - High-performance scientific plotting
- **Backend**: Custom Touchstone parser with NumPy integration
- **Package Management**: uv - Fast, modern Python package management
- **Testing**: pytest - Comprehensive test coverage

### Project Structure

```
SnPViewer/
├── frontend/           # GUI components and user interface
│   ├── widgets/       # Custom Qt widgets (ChartView, SmithView, etc.)
│   ├── dialogs/       # Property dialogs and user interactions
│   └── services/      # Background services and utilities
├── backend/           # Data models and business logic
│   ├── models/        # Data structures (Dataset, Chart, Project, etc.)
│   └── parsing/       # Touchstone file parsing and conversion
├── tests/             # Test suite
└── specs/             # Development specifications and documentation
```

## 🧪 Development

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=backend --cov=frontend

# Run specific test modules
uv run pytest tests/test_parsing.py
```

### Code Quality

```bash
# Linting and formatting
uv run ruff check .
uv run ruff format .

# Type checking (if using mypy)
uv run mypy backend/ frontend/
```

### Development Environment

The project uses modern Python development practices:

- **uv**: Fast dependency resolution and virtual environment management
- **ruff**: Lightning-fast linting and formatting
- **pytest**: Comprehensive testing framework
- **Type hints**: Full type annotation support

## 🤖 AI-Assisted Development

This project was developed with the assistance of **GitHub Copilot** and AI agents, showcasing the power of human-AI collaboration in software development:

- **Architecture Design**: AI-assisted system architecture and component design
- **Feature Implementation**: Collaborative development of complex UI features
- **Code Quality**: AI-powered code review and optimization suggestions
- **Documentation**: AI-assisted documentation and user guide creation
- **Testing**: Automated test case generation and coverage improvement

The combination of human creativity and AI capabilities enabled rapid development of a professional-grade application with comprehensive features and robust architecture.

## 🔮 Roadmap

### Planned Features

- [ ] **Export Capabilities**: PNG, PDF, and SVG chart export
- [ ] **Data Analysis**: Statistical analysis and curve fitting tools
- [ ] **Measurement Automation**: Automated measurement routines
- [ ] **Plugin System**: Extensible plugin architecture
- [ ] **Network Analysis**: Advanced network parameter calculations
- [ ] **Batch Processing**: Automated processing of measurement sets

### Technical Improvements

- [ ] **Performance**: Optimization for large datasets
- [ ] **Accessibility**: Screen reader and keyboard navigation support
- [ ] **Internationalization**: Multi-language support
- [ ] **Cloud Integration**: Cloud storage and sharing capabilities

## 🤝 Contributing

We welcome contributions! Please see our contributing guidelines:

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes (`git commit -m 'Add amazing feature'`)
4. **Push** to the branch (`git push origin feature/amazing-feature`)
5. **Open** a Pull Request

### Development Guidelines

- Follow PEP 8 style guidelines
- Add tests for new features
- Update documentation as needed
- Use type hints for all functions
- Write clear commit messages

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Qt/PySide6**: For providing an excellent cross-platform GUI framework
- **PyQtGraph**: For high-performance scientific plotting capabilities
- **NumPy**: For efficient numerical computing
- **GitHub Copilot**: For AI-assisted development and pair programming
- **RF Engineering Community**: For feedback and feature suggestions

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/SnPViewer/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/SnPViewer/discussions)
- **Email**: your.email@example.com

---

**Made with ❤️ and 🤖 AI assistance using Python, Qt, and modern development practices.**
