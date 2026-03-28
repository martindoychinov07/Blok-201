package com.example.server.model;

import lombok.*;

@Getter
@Setter
@AllArgsConstructor
@NoArgsConstructor
public class Message {
    private String sender;
    private String content;
}