package com.example.server.model;

import jakarta.persistence.*;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.UUID;

@Entity
@Table(name = "users")
@Data
@NoArgsConstructor
public class User {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private UUID id;

    @Column(nullable = false, unique = true, length = 50)
    private String username;

    @Column(nullable = false, length = 255)
    private String password;

    @Column(nullable = false, length = 20)
    @Enumerated(EnumType.STRING)
    private Role role;

    @Column(name = "full_name", length = 100)
    private String fullName;

    @Column(name = "dementia_stage")
    private Integer dementiaStage;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "patient_id")
    private User patient;

    public enum Role {
        USER, CAREGIVER
    }

    public UUID getId() {
        return id;
    }

    public Role getRole() {
        return role;
    }

    public User getPatient() {
        return patient;
    }
}
