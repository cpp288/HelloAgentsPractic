package com.trip.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "agent")
public record AgentProperties(String baseUrl, String internalToken, int timeoutSeconds) {
}
