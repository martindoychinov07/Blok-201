package com.example.server.service;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.*;
import org.springframework.http.client.SimpleClientHttpRequestFactory;
import org.springframework.stereotype.Service;
import org.springframework.web.client.HttpStatusCodeException;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.util.UriComponentsBuilder;

import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;
import tools.jackson.core.type.TypeReference;
import tools.jackson.databind.ObjectMapper;

@Service
public class AiCoreClientService {

    @Autowired
    private ObjectMapper objectMapper;

    @Value("${ai.core.base-url:http://localhost:8001}")
    private String aiBaseUrl;

    @Value("${ai.core.timeout-ms:25000}")
    private int timeoutMs;

    public Map<String, Object> analyzeText(String patientId, String text, Instant timestamp) {
        Map<String, Object> body = new LinkedHashMap<>();
        body.put("patient_id", patientId);
        body.put("timestamp", timestamp.toString());
        body.put("text", text);

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);

        String url = baseUrl() + "/transcripts/analyze";
        return postJson(url, new HttpEntity<>(body, headers));
    }

    public Map<String, Object> transcribeAndAnalyze(String patientId, byte[] wavBytes, Instant timestamp) {
        String url = UriComponentsBuilder
                .fromUriString(baseUrl() + "/transcripts/transcribe")
                .queryParam("patient_id", patientId)
                .queryParam("analyze", "true")
                .queryParam("timestamp", timestamp.toString())
                .build()
                .toUriString();

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.parseMediaType("audio/wav"));
        HttpEntity<byte[]> entity = new HttpEntity<>(wavBytes, headers);

        return postJson(url, entity);
    }

    private Map<String, Object> postJson(String url, HttpEntity<?> entity) {
        RestTemplate restTemplate = restTemplate();
        try {
            ResponseEntity<String> response = restTemplate.exchange(url, HttpMethod.POST, entity, String.class);
            return readJsonMap(response.getBody());
        } catch (HttpStatusCodeException ex) {
            String body = ex.getResponseBodyAsString(StandardCharsets.UTF_8);
            String message = "AI request failed (" + ex.getStatusCode().value() + "): " + compact(body);
            throw new IllegalStateException(message, ex);
        } catch (Exception ex) {
            throw new IllegalStateException("AI request failed: " + compact(ex.getMessage()), ex);
        }
    }

    private RestTemplate restTemplate() {
        SimpleClientHttpRequestFactory factory = new SimpleClientHttpRequestFactory();
        factory.setConnectTimeout(timeoutMs);
        factory.setReadTimeout(timeoutMs);
        return new RestTemplate(factory);
    }

    private Map<String, Object> readJsonMap(String json) {
        try {
            if (json == null || json.isBlank()) {
                return Map.of();
            }
            return objectMapper.readValue(json, new TypeReference<>() {});
        } catch (Exception ex) {
            throw new IllegalStateException("AI response was not valid JSON", ex);
        }
    }

    private String compact(String raw) {
        if (raw == null) {
            return "";
        }
        String v = raw.replaceAll("\\s+", " ").trim();
        if (v.length() > 260) {
            return v.substring(0, 257) + "...";
        }
        return v;
    }

    private String baseUrl() {
        return aiBaseUrl == null ? "http://localhost:8001" : aiBaseUrl.replaceAll("/+$", "");
    }
}
