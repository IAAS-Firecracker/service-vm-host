#!/bin/bash

# Variable globale pour stocker la dernière erreur
LAST_ERROR_LINE=0
LAST_ERROR_TYPE=""
LAST_ERROR_MESSAGE=""

# Fonction pour écrire dans les logs
write_to_log() {
    local log_file="$1"
    local message="$2"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[${timestamp}] $message" >> "$log_file"
}

check_curl_response() {
    local response="$1"
    local action="$2"
    local line_number="$3"
    local log_file="$4"
    
    # Extraire le code HTTP de la réponse
    http_code=$(echo "$response" | head -n 1 | cut -d' ' -f2)
    
    # Créer le message de log
    local log_message=""
    
    # Vérifier si le code est dans la plage 200-299 (succès)
    if [[ $http_code -ge 200 ]] && [[ $http_code -lt 300 ]]; then
        log_message=" Success: $action (HTTP $http_code)"
        echo "$log_message"
        [ -n "$log_file" ] && write_to_log "$log_file" "$log_message"
        return 0
    else
        LAST_ERROR_LINE=$line_number
        case $http_code in
            400)
                LAST_ERROR_TYPE="BAD_REQUEST"
                ;;
            401)
                LAST_ERROR_TYPE="UNAUTHORIZED"
                ;;
            403)
                LAST_ERROR_TYPE="FORBIDDEN"
                ;;
            404)
                LAST_ERROR_TYPE="NOT_FOUND"
                ;;
            409)
                LAST_ERROR_TYPE="CONFLICT"
                ;;
            500)
                LAST_ERROR_TYPE="SERVER_ERROR"
                ;;
            *)
                LAST_ERROR_TYPE="UNKNOWN_ERROR"
                ;;
        esac
        LAST_ERROR_MESSAGE="$response"
        
        # Construire le message d'erreur complet
        log_message=" Error at line $LAST_ERROR_LINE: $LAST_ERROR_TYPE"
        echo "$log_message"
        [ -n "$log_file" ] && write_to_log "$log_file" "$log_message"
        
        log_message="Action: $action failed (HTTP $http_code)"
        echo "$log_message"
        [ -n "$log_file" ] && write_to_log "$log_file" "$log_message"
        
        log_message="Response: $response"
        echo "$log_message"
        [ -n "$log_file" ] && write_to_log "$log_file" "$log_message"
        
        return 1
    fi
}

# Fonction pour obtenir les détails de la dernière erreur
get_last_error() {
    local log_file="$1"
    if [ $LAST_ERROR_LINE -ne 0 ]; then
        local messages=(
            "Last Error Details:"
            "Line Number: $LAST_ERROR_LINE"
            "Error Type: $LAST_ERROR_TYPE"
            "Error Message: $LAST_ERROR_MESSAGE"
        )
        
        for message in "${messages[@]}"; do
            echo "$message"
            [ -n "$log_file" ] && write_to_log "$log_file" "$message"
        done
    fi
}
