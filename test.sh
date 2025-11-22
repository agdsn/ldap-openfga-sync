#!/bin/bash
# Test environment management script

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

function print_header() {
    echo -e "\n${GREEN}===================================================${NC}"
    echo -e "${GREEN}$1${NC}"
    echo -e "${GREEN}===================================================${NC}\n"
}

function print_error() {
    echo -e "${RED}❌ $1${NC}"
}

function print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

function print_info() {
    echo -e "${YELLOW}ℹ️  $1${NC}"
}

function start_services() {
    print_header "Starting Test Environment"

    print_info "Starting Docker containers..."
    docker compose up -d

    print_info "Waiting for services to be ready..."
    sleep 5

    # Check LDAP
    if docker compose exec -T ldap ldapsearch -x -H ldap://localhost -b "dc=example,dc=com" -D "cn=admin,dc=example,dc=com" -w admin > /dev/null 2>&1; then
        print_success "LDAP is running"
    else
        print_error "LDAP failed to start"
        return 1
    fi

    # Check OpenFGA
    if curl -s http://localhost:8080/healthz > /dev/null 2>&1; then
        print_success "OpenFGA is running"
    else
        print_error "OpenFGA failed to start"
        return 1
    fi

    print_success "Test environment is ready!"
}

function stop_services() {
    print_header "Stopping Test Environment"
    docker compose down -v
    print_success "Test environment stopped"
}

function run_tests() {
    print_header "Running Test Suite"

    # Make sure services are running
    if ! docker compose ps | grep -q "Up"; then
        print_info "Services not running, starting them..."
        start_services
    fi

    # Run tests
    source .venv/bin/activate
    python test_suite.py

    TEST_EXIT_CODE=$?

    if [ $TEST_EXIT_CODE -eq 0 ]; then
        print_success "All tests passed!"
    else
        print_error "Some tests failed"
    fi

    return $TEST_EXIT_CODE
}

function clean_restart() {
    print_header "Clean Restart"
    stop_services
    start_services
}

function show_logs() {
    print_header "Service Logs"
    docker compose logs -f
}

function show_ldap_data() {
    print_header "LDAP Data"
    print_info "Groups and Members:"
    docker compose exec ldap ldapsearch -x -H ldap://localhost \
        -b "ou=groups,dc=example,dc=com" \
        -D "cn=admin,dc=example,dc=com" \
        -w admin \
        "(objectClass=groupOfNames)" \
        cn member
}

function show_usage() {
    cat << EOF
Usage: $0 [command]

Commands:
    start       Start the test environment (LDAP + OpenFGA)
    stop        Stop the test environment
    restart     Clean restart of the environment
    test        Run the test suite
    logs        Show service logs
    ldap        Show LDAP data
    help        Show this help message

Examples:
    $0 start          # Start services
    $0 test           # Run all tests
    $0 restart test   # Clean restart and run tests
    $0 logs           # Watch service logs

EOF
}

# Main script
case "${1:-help}" in
    start)
        start_services
        ;;
    stop)
        stop_services
        ;;
    restart)
        clean_restart
        if [ "$2" == "test" ]; then
            run_tests
        fi
        ;;
    test)
        run_tests
        ;;
    logs)
        show_logs
        ;;
    ldap)
        show_ldap_data
        ;;
    help|*)
        show_usage
        exit 0
        ;;
esac

