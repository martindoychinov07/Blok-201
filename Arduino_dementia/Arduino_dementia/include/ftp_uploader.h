#pragma once

#include <Arduino.h>
#include <Client.h>

class FtpUploader {
 public:
  FtpUploader(Client& controlClient, Client& dataClient);

  bool begin(const char* host,
             uint16_t port,
             const char* user,
             const char* pass,
             uint32_t ackNumber);
  bool uploadFile(const char* localPath, const char* remoteName);

 private:
  bool ensureSession();
  bool enterPassiveMode(String& ip, uint16_t& port);
  bool sendCommand(const String& cmd,
                   int expectedA,
                   int expectedB,
                   String* outLine,
                   uint32_t timeoutMs);
  bool readReply(int& code, String& line, uint32_t timeoutMs);

  Client& ctrl_;
  Client& data_;
  String host_;
  String user_;
  String pass_;
  String remoteDir_;
  uint16_t port_ = 21;
};
