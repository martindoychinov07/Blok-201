package com.example.server.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.eclipse.paho.client.mqttv3.MqttConnectOptions;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.integration.channel.DirectChannel;
import org.springframework.integration.config.EnableIntegration;
import org.springframework.integration.core.MessageProducer;
import org.springframework.integration.annotation.ServiceActivator;
import org.springframework.messaging.MessageChannel;
import org.springframework.messaging.MessageHandler;

import org.springframework.integration.mqtt.core.DefaultMqttPahoClientFactory;
import org.springframework.integration.mqtt.core.MqttPahoClientFactory;
import org.springframework.integration.mqtt.inbound.MqttPahoMessageDrivenChannelAdapter;
import org.springframework.integration.mqtt.outbound.MqttPahoMessageHandler;
import org.springframework.integration.mqtt.support.DefaultPahoMessageConverter;

@Configuration
@EnableIntegration
public class MqttConfig {
    private static final String[] SUBSCRIBED_TOPICS = {
            "device/hello",
            "sensor/data",
            "sensor/+"
    };

    @Value("${mqtt.broker-uri:tcp://localhost:1883}")
    private String mqttBrokerUri;

    @Value("${mqtt.inbound-client-id:spring-server-client}")
    private String inboundClientId;

    @Value("${mqtt.outbound-client-id:spring-server-publisher}")
    private String outboundClientId;

    @Bean
    public MessageChannel mqttInputChannel() {
        return new DirectChannel();
    }

    @Bean
    public MessageChannel mqttOutboundChannel() {
        return new DirectChannel();
    }

    @Bean
    public MqttPahoClientFactory mqttClientFactory() {
        DefaultMqttPahoClientFactory factory = new DefaultMqttPahoClientFactory();

        MqttConnectOptions options = new MqttConnectOptions();
        options.setServerURIs(new String[]{mqttBrokerUri});
        options.setCleanSession(true);
        options.setKeepAliveInterval(60);
        factory.setConnectionOptions(options);
        return factory;
    }

    @Bean
    public MessageProducer inbound() {
        MqttPahoMessageDrivenChannelAdapter adapter =
                new MqttPahoMessageDrivenChannelAdapter(
                        inboundClientId,
                        mqttClientFactory(),
                        SUBSCRIBED_TOPICS
                );

        adapter.setQos(1);
        adapter.setConverter(new DefaultPahoMessageConverter());
        adapter.setOutputChannel(mqttInputChannel());

        return adapter;
    }

    @Bean
    @ServiceActivator(inputChannel = "mqttOutboundChannel")
    public MessageHandler mqttOutbound() {
        MqttPahoMessageHandler handler = new MqttPahoMessageHandler(outboundClientId, mqttClientFactory());
        handler.setAsync(true);
        handler.setDefaultQos(1);
        handler.setDefaultRetained(false);
        handler.setConverter(new DefaultPahoMessageConverter());
        return handler;
    }
}
