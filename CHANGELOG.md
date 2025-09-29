# Changelog

All notable changes to SnPViewer will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### 🎉 Major Features

- **Complete RF Touchstone Viewer**: Professional-grade S-parameter visualization
- **Advanced Chart System**: Magnitude, Phase, Group Delay, and Smith Chart support
- **Comprehensive Limit Lines**: 5 types with flexible input parsing and styling
- **Professional Styling**: Excel-like plot area controls, font styling, trace properties
- **Project Management**: Complete save/load with unsaved changes protection
- **Interactive Features**: Markers, zoom, pan, and real-time measurements

### ✨ Chart Types & Visualization

- Magnitude plots with dB and linear scaling
- Phase plots with degree and radian options
- Group delay analysis for time-domain insights
- Interactive Smith charts for reflection coefficient visualization
- Multi-trace support for parameter comparison
- Interactive markers with coordinate readouts

### 🎯 Advanced Limit Lines System

- **Horizontal Limits**: Simple pass/fail thresholds
- **Vertical Limits**: Frequency-based boundaries
- **Point-based Limits**: Complex limit shapes with coordinate pairs
- **Horizontal Ranges**: Filled pass/fail regions for values
- **Vertical Ranges**: Filled frequency band specifications
- **Smart Input Parsing**: Supports 1e9, 1G, 2.4GHz formats
- **Custom Styling**: Color, line style, width, and labels
- **Range Validation**: Helpful error messages and input guidance

### 🎨 Professional Styling & Customization

- **Trace Properties**: Individual color, style, and width control
- **Font Styling System**: Complete typography control for all chart elements
  - Title fonts and colors
  - Axis label fonts and colors
  - Tick label fonts and colors
  - Legend fonts and colors
- **Plot Area Properties**: Excel-style formatting controls
  - Background colors and patterns
  - Border control (standard, full, none)
  - Grid appearance and transparency
  - Tick label visibility options
- **Project Persistence**: All styling saved and restored with projects

### 💾 Project Management

- **Complete Project System**: Save/load entire analysis sessions
- **Unsaved Changes Protection**: Comprehensive modification tracking
  - Chart creation/deletion
  - Dataset loading/removal
  - All styling and property changes
  - Limit line modifications
- **Auto-save**: Background protection against data loss
- **Recent Files**: Quick access to projects and data files
- **Session Restoration**: Restore complete working state

### 🔧 File Format & Data Support

- **Touchstone v1/v2**: Full format compliance
- **Multi-port Networks**: 1-port to 99-port support (.s1p to .s99p)
- **Custom Parser**: High-performance native implementation
- **Batch Loading**: Folder-based data loading
- **Format Validation**: Comprehensive error checking and reporting

### 🏗️ Architecture & Quality

- **Modern Tech Stack**: PySide6 + PyQtGraph + NumPy
- **Signal-Slot Architecture**: Robust event handling
- **Type Safety**: Comprehensive type hints throughout
- **Test Coverage**: Extensive test suite with pytest
- **Code Quality**: Ruff linting and formatting
- **Package Management**: Modern uv-based dependency management

### 🤖 AI-Assisted Development

- **GitHub Copilot**: AI-assisted feature development
- **Collaborative Design**: Human-AI partnership in architecture
- **Code Quality**: AI-powered review and optimization
- **Documentation**: AI-assisted user guides and technical docs

### 🔧 Technical Improvements

- **Performance**: Optimized for large datasets
- **Memory Management**: Efficient data handling
- **Error Handling**: Comprehensive error catching and user feedback
- **Cross-platform**: Windows, macOS, and Linux support
- **Accessibility**: Keyboard navigation and screen reader support

### 🐛 Bug Fixes

- Fixed border line visibility when tick labels are hidden
- Resolved limit line property restoration from saved projects
- Corrected frequency input parsing with engineering suffixes
- Fixed chart property synchronization with project models
- Resolved memory leaks in chart widget management

### 📚 Documentation

- Comprehensive README with feature overview
- Detailed contributing guidelines
- Architecture documentation
- User guides and tutorials
- API documentation for developers

---

**Initial Release**: This represents the first comprehensive release of SnPViewer, developed from scratch with modern Python practices and AI assistance. The application provides professional-grade RF measurement visualization with advanced features typically found in commercial tools.

**Development Stats**:

- **Lines of Code**: ~15,000+ lines of Python
- **Test Coverage**: Comprehensive test suite
- **Development Time**: Accelerated with AI assistance
- **Architecture**: Modern, maintainable, and extensible
