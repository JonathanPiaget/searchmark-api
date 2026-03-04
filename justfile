# List available recipes
default:
    @just --list

# Install the virtual environment and install the pre-commit hooks
install:
    echo "🚀 Creating virtual environment using uv"
    uv sync
    uv run pre-commit install

# Run code quality tools
check:
    echo "🚀 Checking lock file consistency with 'pyproject.toml'"
    uv lock --locked
    echo "🚀 Linting code: Running pre-commit"
    uv run pre-commit run -a

# Test the code with pytest
test:
    echo "🚀 Testing code: Running pytest"
    uv run python -m pytest --doctest-modules

# Build wheel file
build: clean-build
    echo "🚀 Creating wheel file"
    uvx --from build pyproject-build --installer uv

# Clean build artifacts
clean-build:
    echo "🚀 Removing build artifacts"
    rm -rf dist

# Get a folder recommendation for a URL
recommend url *flags:
    uv run searchmark {{url}} {{flags}}

# Run the github actions locally using act
ci:
    echo "🚀 Running GitHub Actions locally using act"
    act push
