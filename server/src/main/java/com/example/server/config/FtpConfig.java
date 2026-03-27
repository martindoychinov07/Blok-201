package com.example.server.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.integration.ftp.session.DefaultFtpSessionFactory;

@Configuration
public class FtpConfig {

    @Bean
    public DefaultFtpSessionFactory ftpSessionFactory() {
        DefaultFtpSessionFactory factory = new DefaultFtpSessionFactory();

        factory.setHost("localhost");
        factory.setPort(2121);

        factory.setUsername("user");
        factory.setPassword("12345");

        factory.setClientMode(2);

        factory.setConnectTimeout(10000);

        return factory;
    }
}