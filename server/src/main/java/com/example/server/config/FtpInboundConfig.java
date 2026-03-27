package com.example.server.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.integration.dsl.IntegrationFlow;
import org.springframework.integration.ftp.dsl.Ftp;
import org.springframework.integration.ftp.session.DefaultFtpSessionFactory;

import java.io.File;

@Configuration
public class FtpInboundConfig {

    @Bean
    public IntegrationFlow ftpInboundFlow(DefaultFtpSessionFactory sessionFactory) {
        return IntegrationFlow
                .from(Ftp.inboundAdapter(sessionFactory)
                                .remoteDirectory("/esp/audio")
                                .localDirectory(new File("./audio-downloads"))
                                .autoCreateLocalDirectory(true)
                                .regexFilter(".*\\.(mp3|wav|aac)$")
                                .deleteRemoteFiles(false),
                        e -> e.poller(p -> p.fixedDelay(5000)))
                .handle(message -> {
                    File file = (File) message.getPayload();
                    System.out.println("Received audio: " + file.getName());

                    processAudio(file);
                })
                .get();
    }

    private void processAudio(File file) {
        File processedDir = new File("./audio-processed");
        if (!processedDir.exists()) processedDir.mkdirs();

        boolean success = file.renameTo(new File(processedDir, file.getName()));
        if (success) {
            System.out.println("Moved " + file.getName() + " to processed folder");
        }
    }
}