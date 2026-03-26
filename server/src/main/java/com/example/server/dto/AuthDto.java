package com.example.server.dto;


import com.example.server.model.User;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import lombok.Data;

import java.util.UUID;


public class AuthDto {

    @Data
    public static class SignupRequest {
        @NotBlank(message = "Username is required")
        @Size(min = 3, max = 50, message = "Username must be between 3 and 50 characters")
        private String username;

        @NotBlank(message = "Password is required")
        @Size(min = 6, message = "Password must be at least 6 characters")
        private String password;

        @NotNull(message = "Role is required")
        private User.Role role;

        @Size(max = 100)
        private String fullName;

        private UUID patientId;
    }

    @Data
    public static class LoginRequest {
        @NotBlank(message = "Username is required")
        private String username;

        @NotBlank(message = "Password is required")
        private String password;
    }


    @Data
    public static class AuthResponse {
        private UUID id;
        private String username;
        private String fullName;
        private User.Role role;
        private String message;

        public AuthResponse(User user, String message) {
            this.id = user.getId();
            this.username = user.getUsername();
            this.fullName = user.getFullName();
            this.role = user.getRole();
            this.message = message;
        }
    }

    @Data
    public static class ErrorResponse {
        private String error;
        public ErrorResponse(String error) { this.error = error; }
    }
}
