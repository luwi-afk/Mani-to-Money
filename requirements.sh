#!/bin/bash
# requirements.sh
# RPi5 Complete Installation Script for Python 3.11
# For: ncnn, opencv-python, pillow, numpy, reportlab, PyQt5, pyserial

set -e  # Exit on error

echo "========================================="
echo "  Starting installation on Raspberry Pi 5"
echo "  Python 3.11 Version"
echo "========================================="

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[+]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

print_error() {
    echo -e "${RED}[x]${NC} $1"
}

# Check Python version
check_python_version() {
    print_status "Checking Python version..."
    
    # Get Python version
    PY_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
    
    if [[ "$PY_VERSION" == "3.11" ]]; then
        print_status "Python 3.11 detected - good!"
    else
        print_warning "Python $PY_VERSION detected. This script is optimized for Python 3.11"
        print_warning "Continuing anyway, but paths may need adjustment..."
    fi
    
    # Get full Python version for path
    PY_VERSION_FULL=$(python3 --version 2>&1 | cut -d' ' -f2)
    print_status "Python version: $PY_VERSION_FULL"
}

# Check if running on Raspberry Pi 5
check_rpi5() {
    if grep -q "Raspberry Pi 5" /proc/device-tree/model 2>/dev/null; then
        print_status "Raspberry Pi 5 detected"
    else
        print_warning "Not running on RPi5, but script will continue"
    fi
}

# Update system first
update_system() {
    print_status "Updating package lists..."
    sudo apt update
    
    print_status "Upgrading existing packages..."
    sudo apt upgrade -y
}

# Install system dependencies
install_system_deps() {
    print_status "Installing system dependencies..."
    
    # Basic build tools
    sudo apt install -y \
        build-essential \
        cmake \
        git \
        wget \
        curl \
        python3-dev \
        python3-pip \
        python3-venv \
        python3-full \
        python3.11-dev \
        python3.11-venv
        
    # Qt5 dependencies (for PyQt5)
    print_status "Installing Qt5 dependencies..."
    sudo apt install -y \
        qtbase5-dev \
        qt5-qmake \
        qtchooser \
        qtbase5-dev-tools \
        libqt5core5a \
        libqt5gui5 \
        libqt5widgets5 \
        libqt5dbus5 \
        libqt5network5 \
        libqt5svg5-dev \
        libqt5xml5 \
        libqt5test5
        
    # OpenCV dependencies - removed problematic qt4 packages
    print_status "Installing OpenCV dependencies..."
    sudo apt install -y \
        libhdf5-dev \
        libhdf5-serial-dev \
        libatlas-base-dev \
        libjasper-dev \
        libavcodec-dev \
        libavformat-dev \
        libswscale-dev \
        libv4l-dev \
        libxvidcore-dev \
        libx264-dev \
        libgtk-3-dev \
        libcanberra-gtk3-module \
        libilmbase-dev \
        libopenexr-dev \
        libgstreamer1.0-dev \
        libgstreamer-plugins-base1.0-dev
        
    # ncnn dependencies
    print_status "Installing ncnn dependencies..."
    sudo apt install -y \
        libprotobuf-dev \
        protobuf-compiler
        
    # ReportLab dependencies
    sudo apt install -y \
        python3-tk \
        libfreetype6-dev \
        libjpeg-dev \
        zlib1g-dev
        
    print_status "System dependencies installed"
}

# Install Python packages via pip (safe ones first)
install_pip_packages() {
    print_status "Installing Python packages via pip..."
    
    # Upgrade pip first
    python3 -m pip install --upgrade pip
    
    # Install basic packages (these usually work fine)
    print_status "Installing numpy, pillow, reportlab..."
    pip3 install \
        "numpy>=1.24.0" \
        "pillow>=9.0.0" \
        "reportlab>=3.6.0"
    
    # Install pyserial
    print_status "Installing pyserial..."
    pip3 install pyserial
    
    # Install opencv-python (special handling for RPi)
    print_status "Installing opencv-python (this may take a few minutes)..."
    pip3 install "opencv-python>=4.8.0"
}

# Install PyQt5 (special handling)
install_pyqt5() {
    print_status "Installing PyQt5 (via apt for stability)..."
    
    # Use apt for PyQt5 (much more reliable on RPi than pip)
    sudo apt install -y python3-pyqt5 python3-pyqt5.qtsvg python3-pyqt5.qtwebkit
    
    # Verify PyQt5 installation
    python3 -c "
import sys
try:
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import QT_VERSION_STR
    print(f'✓ PyQt5 installed successfully (Qt version: {QT_VERSION_STR})')
except ImportError as e:
    print(f'✗ PyQt5 installation failed: {e}')
    sys.exit(1)
" 2>/dev/null
    
    if [ $? -eq 0 ]; then
        print_status "PyQt5 installed successfully"
    else
        print_warning "PyQt5 apt installation had issues, trying pip in virtual environment..."
        
        # Create virtual environment as fallback
        python3 -m venv ~/pyqt_env
        source ~/pyqt_env/bin/activate
        pip install pyqt5
        deactivate
        
        print_warning "PyQt5 installed in virtual environment at ~/pyqt_env"
        print_warning "Activate with: source ~/pyqt_env/bin/activate"
    fi
}

# Install ncnn from source (most complex)
install_ncnn() {
    print_status "Installing ncnn from source (this will take 15-30 minutes)..."
    
    # Create temp directory
    cd ~
    if [ -d "ncnn" ]; then
        print_warning "ncnn directory already exists, removing..."
        rm -rf ncnn
    fi
    
    # Clone ncnn repository
    print_status "Cloning ncnn repository..."
    git clone --depth=1 https://github.com/Tencent/ncnn.git
    cd ncnn
    git submodule update --init --recursive
    
    # Create build directory
    mkdir -p build && cd build
    
    # Detect architecture
    ARCH=$(uname -m)
    print_status "Detected architecture: $ARCH"
    
    # Configure CMake based on architecture
    if [ "$ARCH" = "aarch64" ]; then
        print_status "Configuring for 64-bit RPi5..."
        cmake -DCMAKE_BUILD_TYPE=Release \
              -DNCNN_VULKAN=OFF \
              -DNCNN_BUILD_EXAMPLES=ON \
              -DNCNN_PYTHON=ON \
              -DNCNN_OPENMP=ON \
              -DNCNN_BUILD_TOOLS=ON \
              -DNCNN_BUILD_BENCHMARK=ON \
              -DPYTHON_EXECUTABLE=$(which python3) \
              -DPYTHON_INCLUDE_DIR=$(python3 -c "from sysconfig import get_path; print(get_path('include'))") \
              -DPYTHON_LIBRARY=$(python3 -c "from sysconfig import get_config_var; print(get_config_var('LIBDIR'))") \
              -DCMAKE_TOOLCHAIN_FILE=../toolchains/aarch64-linux-gnu.toolchain.cmake ..
    else
        print_status "Configuring for 32-bit RPi5..."
        cmake -DCMAKE_BUILD_TYPE=Release \
              -DNCNN_VULKAN=OFF \
              -DNCNN_BUILD_EXAMPLES=ON \
              -DNCNN_PYTHON=ON \
              -DNCNN_OPENMP=ON \
              -DNCNN_BUILD_TOOLS=ON \
              -DNCNN_BUILD_BENCHMARK=ON \
              -DPYTHON_EXECUTABLE=$(which python3) \
              -DPYTHON_INCLUDE_DIR=$(python3 -c "from sysconfig import get_path; print(get_path('include'))") \
              -DPYTHON_LIBRARY=$(python3 -c "from sysconfig import get_config_var; print(get_config_var('LIBDIR'))") \
              -DPI5=ON \
              -DCMAKE_TOOLCHAIN_FILE=../toolchains/pi3.toolchain.cmake ..
    fi
    
    # Compile (use all 4 cores on RPi5)
    print_status "Compiling ncnn (using all 4 cores)..."
    make -j4
    
    # Install
    print_status "Installing ncnn..."
    sudo make install
    sudo ldconfig
    
    # Install Python bindings
    print_status "Installing ncnn Python bindings..."
    
    # Find the Python bindings
    NCNN_PYTHON_PATH=$(find ~/ncnn/build -name "ncnn*.so" -exec dirname {} \; | head -1)
    
    if [ -n "$NCNN_PYTHON_PATH" ]; then
        print_status "Found ncnn Python bindings at: $NCNN_PYTHON_PATH"
        
        # Get Python site-packages path
        PYTHON_SITE=$(python3 -c "import site; print(site.getusersitepackages())")
        mkdir -p "$PYTHON_SITE"
        
        # Copy the .so file to site-packages
        cp "$NCNN_PYTHON_PATH"/*ncnn*.so "$PYTHON_SITE/"
        
        # Also copy any .py files
        cp "$NCNN_PYTHON_PATH"/*.py "$PYTHON_SITE/" 2>/dev/null || true
        
        # Add to Python path in bashrc
        echo "export PYTHONPATH=\"$PYTHON_SITE:\$PYTHONPATH\"" >> ~/.bashrc
        
        print_status "ncnn Python bindings installed to $PYTHON_SITE"
    else
        print_warning "Could not find ncnn Python bindings, building manually..."
        
        # Try building Python bindings manually
        cd ~/ncnn
        pip install .
    fi
    
    print_status "ncnn installation complete"
}

# Verify all installations
verify_installations() {
    print_status "Verifying all installations..."
    
    # Create verification script with Python 3.11 specifics
    cat > ~/verify_install.py << 'EOF'
#!/usr/bin/env python3
import sys
import importlib.metadata

def check_import(module_name, min_version=None):
    try:
        # Special handling for different import names
        import_map = {
            'cv2': 'cv2',
            'PIL': 'PIL',
            'serial': 'serial',
            'PyQt5': 'PyQt5',
            'ncnn': 'ncnn'
        }
        
        import_name = import_map.get(module_name, module_name)
        
        if module_name == 'cv2':
            import cv2 as module
            version = cv2.__version__
        elif module_name == 'PIL':
            from PIL import Image
            import PIL
            version = PIL.__version__
        elif module_name == 'PyQt5':
            from PyQt5.QtCore import QT_VERSION_STR
            version = QT_VERSION_STR
            module = sys.modules['PyQt5']
        else:
            module = __import__(import_name)
            if hasattr(module, '__version__'):
                version = module.__version__
            else:
                try:
                    version = importlib.metadata.version(module_name)
                except:
                    version = 'unknown'
        
        if min_version:
            print(f"✓ {module_name} {version} >= {min_version}")
        else:
            print(f"✓ {module_name} {version}")
        return True
    except ImportError as e:
        print(f"✗ {module_name}: NOT INSTALLED ({e})")
        return False
    except Exception as e:
        print(f"✗ {module_name}: ERROR ({e})")
        return False

print("\n=== Installation Verification (Python 3.11) ===\n")
print(f"Python version: {sys.version}\n")

# Check all packages
checks = [
    ('numpy', '1.24.0'),
    ('cv2', '4.8.0'),
    ('PIL', '9.0.0'),
    ('reportlab', '3.6.0'),
    ('PyQt5', '5.15.0'),
    ('serial', None),  # pyserial
    ('ncnn', '1.0.0')
]

success = True
for module, min_version in checks:
    if not check_import(module, min_version):
        success = False

print("\n=== Summary ===")
if success:
    print("✅ All packages installed successfully!")
    sys.exit(0)
else:
    print("❌ Some packages failed to install")
    print("\nTroubleshooting tips:")
    print("1. For PyQt5: Try: sudo apt install python3-pyqt5")
    print("2. For ncnn: Check ~/ncnn/build for compilation errors")
    print("3. For OpenCV: Try: pip install opencv-python --no-cache-dir")
    sys.exit(1)
EOF

    chmod +x ~/verify_install.py
    python3 ~/verify_install.py
}

# Create Python 3.11 alias if needed
setup_python_alias() {
    if ! command -v python &> /dev/null; then
        print_status "Creating python alias for python3..."
        sudo update-alternatives --install /usr/bin/python python /usr/bin/python3 1
    fi
}

# Main installation function
main() {
    print_status "Starting installation process for Python 3.11..."
    
    check_rpi5
    check_python_version
    setup_python_alias
    update_system
    install_system_deps
    install_pip_packages
    install_pyqt5
    install_ncnn
    
    print_status "Installation complete! Verifying..."
    verify_installations
    
    print_status "You may need to run: source ~/.bashrc"
    print_status "Or log out and back in for Python path changes to take effect"
    
    echo ""
    echo "========================================="
    echo "  Installation completed on $(date)"
    echo "  Python 3.11 environment ready"
    echo "========================================="
    
    # Final instructions
    echo ""
    echo "📝 Next steps:"
    echo "1. Run: source ~/.bashrc"
    echo "2. Test your imports: python3 -c \"import ncnn; print('ncnn OK')\""
    echo "3. If PyQt5 installed in venv: source ~/pyqt_env/bin/activate"
}

# Run main function
main