#!/usr/bin/env bash

message_info() {
    echo -e "\033[0;36m${1}\033[0m"
}

message_success() {
    echo -e "\033[0;32m${1}\033[0m"
}

message_warning() {
    echo -e "\033[0;33m${1}\033[0m"
}

message_error() {
    echo -e "\033[0;31m${1}\033[0m"
}
