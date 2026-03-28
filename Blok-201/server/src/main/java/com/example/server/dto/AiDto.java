package com.example.server.dto;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.Map;

public class AiDto {

    public static class EmbeddedTextRequest {
        @JsonProperty("patient_id")
        public String patientId;
        public String text;
        public String timestamp;
        public Map<String, Object> sensor;
    }

    public static class StatusUpdateRequest {
        public String status;
    }
}
