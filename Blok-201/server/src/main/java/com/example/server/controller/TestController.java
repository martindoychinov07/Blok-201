package com.example.server.controller;

import com.example.server.model.Message;
import org.springframework.messaging.handler.annotation.MessageMapping;
import org.springframework.messaging.handler.annotation.SendTo;
import org.springframework.stereotype.Controller;

@Controller
public class TestController {

    @MessageMapping("/send") // client sends to /app/send
    @SendTo("/topic/messages") // broadcast to subscribers
    public Message sendMessage(Message message) {
        return message;
    }
}