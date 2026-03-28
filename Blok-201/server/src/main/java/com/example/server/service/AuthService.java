package com.example.server.service;

import com.example.server.dto.AuthDto;
import com.example.server.model.User;
import com.example.server.repository.UserRepository;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpSession;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContext;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.web.context.HttpSessionSecurityContextRepository;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.context.request.RequestContextHolder;
import org.springframework.web.context.request.ServletRequestAttributes;

@Service
public class AuthService {

    private UserRepository userRepository;
    private PasswordEncoder passwordEncoder;
    private AuthenticationManager authenticationManager;

    @Autowired
    public AuthService(
            UserRepository userRepository,
            PasswordEncoder passwordEncoder,
            AuthenticationManager authenticationManager
    ) {
        this.userRepository = userRepository;
        this.passwordEncoder = passwordEncoder;
        this.authenticationManager = authenticationManager;
    }

    @Transactional
    public AuthDto.AuthResponse signup(AuthDto.SignupRequest request) {

        if (userRepository.existsByUsername(request.getUsername())) {
            throw new IllegalArgumentException(
                    "Username '" + request.getUsername() + "' is already taken");
        }

        User user = new User();
        user.setUsername(request.getUsername());
        user.setPassword(passwordEncoder.encode(request.getPassword()));
        user.setRole(request.getRole());
        user.setFullName(request.getFullName());

        if (request.getRole() == User.Role.USER) {
            if (request.getDementiaStage() == null) {
                throw new IllegalArgumentException(
                        "Dementia stage (1 or 2) is required for USER accounts");
            }
            user.setDementiaStage(request.getDementiaStage());
        }

        if (request.getRole() == User.Role.CAREGIVER) {
            if (request.getPatientId() == null) {
                throw new IllegalArgumentException(
                        "A patient ID is required when registering as a custodian");
            }
            User patient = userRepository.findById(request.getPatientId())
                    .orElseThrow(() -> new IllegalArgumentException(
                            "Patient not found with id: " + request.getPatientId()));

            if (patient.getRole() != User.Role.USER) {
                throw new IllegalArgumentException(
                        "The linked patient_id must belong to a USER (patient) role account");
            }
            user.setPatient(patient);
        }

        User saved = userRepository.save(user);

        Authentication authentication = authenticationManager.authenticate(
                new UsernamePasswordAuthenticationToken(
                        request.getUsername(), request.getPassword()));
        SecurityContext context = SecurityContextHolder.createEmptyContext();
        context.setAuthentication(authentication);
        SecurityContextHolder.setContext(context);
        persistContextInHttpSession(context);

        return new AuthDto.AuthResponse(saved, "Registration successful");
    }

    public AuthDto.AuthResponse login(AuthDto.LoginRequest request) {
        Authentication authentication = authenticationManager.authenticate(
                new UsernamePasswordAuthenticationToken(
                        request.getUsername(), request.getPassword()));

        SecurityContext context = SecurityContextHolder.createEmptyContext();
        context.setAuthentication(authentication);
        SecurityContextHolder.setContext(context);
        persistContextInHttpSession(context);

        User user = userRepository.findByUsername(request.getUsername())
                .orElseThrow(() -> new IllegalArgumentException("User not found"));

        return new AuthDto.AuthResponse(user, "Login successful");
    }

    public void logout(HttpServletRequest request) throws Exception {
        request.logout();
        SecurityContextHolder.clearContext();
    }

    private void persistContextInHttpSession(SecurityContext context) {
        ServletRequestAttributes attrs = (ServletRequestAttributes) RequestContextHolder.getRequestAttributes();
        if (attrs == null) {
            return;
        }
        HttpSession session = attrs.getRequest().getSession(true);
        session.setAttribute(HttpSessionSecurityContextRepository.SPRING_SECURITY_CONTEXT_KEY, context);
    }
}
