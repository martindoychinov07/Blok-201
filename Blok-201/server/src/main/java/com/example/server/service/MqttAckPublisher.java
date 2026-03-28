package com.example.server.service;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.integration.mqtt.support.MqttHeaders;
import org.springframework.messaging.Message;
import org.springframework.messaging.MessageChannel;
import org.springframework.messaging.support.MessageBuilder;
import org.springframework.stereotype.Service;

@Service
public class MqttAckPublisher {

    @Autowired
    private MessageChannel mqttOutboundChannel;

    public void publish(String topic, String jsonPayload) {
        if (topic == null || topic.isBlank() || jsonPayload == null) {
            return;
        }
        Message<String> msg = MessageBuilder
                .withPayload(jsonPayload)
                .setHeader(MqttHeaders.TOPIC, topic)
                .setHeader(MqttHeaders.QOS, 1)
                .build();
        mqttOutboundChannel.send(msg);
    }
}
