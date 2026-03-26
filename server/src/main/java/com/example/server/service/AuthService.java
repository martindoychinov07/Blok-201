package com.example.server.service;

import com.example.server.dto.AuthDto;
import com.example.server.model.User;
import com.example.server.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@RequiredArgsConstructor
public class AuthService {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;

    @Transactional
    public AuthDto.AuthResponse signup(AuthDto.SignupRequest request) {
        if (userRepository.existsByUsername(request.getUsername())) {
            throw new IllegalArgumentException("Username '" + request.getUsername() + "' is already taken");
        }

        User user = new User();
        user.setUsername(request.getUsername());
        user.setPassword(passwordEncoder.encode(request.getPassword()));
        user.setRole(request.getRole());
        user.setFullName(request.getFullName());

        if (request.getRole() == User.Role.CAREGIVER && request.getPatientId() != null) {
            User patient = userRepository.findById(request.getPatientId())
                    .orElseThrow(() -> new IllegalArgumentException("Patient not found with id: " + request.getPatientId()));

            if (patient.getRole() != User.Role.USER) {
                throw new IllegalArgumentException("The linked patient_id must belong to a USER role account");
            }
            user.setPatient(patient);
        }

        User saved = userRepository.save(user);
        return new AuthDto.AuthResponse(saved, "Registration successful");
    }

    public AuthDto.AuthResponse login(AuthDto.LoginRequest request) {
        User user = userRepository.findByUsername(request.getUsername())
                .orElseThrow(() -> new IllegalArgumentException("Invalid username or password"));

        if (!passwordEncoder.matches(request.getPassword(), user.getPassword())) {
            throw new IllegalArgumentException("Invalid username or password");
        }

        return new AuthDto.AuthResponse(user, "Login successful");
    }
}