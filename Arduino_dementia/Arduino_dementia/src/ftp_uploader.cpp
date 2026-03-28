#include "ftp_uploader.h"

#include <SD.h>

FtpUploader::FtpUploader(Client& controlClient, Client& dataClient)
    : ctrl_(controlClient), data_(dataClient) {}

bool FtpUploader::begin(const char* host,
                       uint16_t port,
                       const char* user,
                       const char* pass,
                       uint32_t ackNumber) {
  host_ = host;
  port_ = port;
  user_ = user;
  pass_ = pass;
  remoteDir_ = "/" + String(ackNumber);
  return ensureSession();
}

bool FtpUploader::uploadFile(const char* localPath, const char* remoteName) {
  if (!ensureSession()) {
    return false;
  }

  File in = SD.open(localPath, FILE_READ);
  if (!in) {
    Serial.printf("[FTP] Cannot open local file: %s\n", localPath);
    return false;
  }

  String dataIp;
  uint16_t dataPort = 0;
  if (!enterPassiveMode(dataIp, dataPort)) {
    in.close();
    return false;
  }

  if (!data_.connect(dataIp.c_str(), dataPort)) {
    Serial.println("[FTP] Data channel connect failed");
    in.close();
    return false;
  }

  String reply;
  if (!sendCommand("STOR " + String(remoteName), 150, 125, &reply, 15000)) {
    data_.stop();
    in.close();
    return false;
  }

  uint8_t buffer[1024];
  while (in.available()) {
    const size_t readLen = in.read(buffer, sizeof(buffer));
    if (readLen == 0) {
      break;
    }
    const size_t sent = data_.write(buffer, readLen);
    if (sent != readLen) {
      Serial.println("[FTP] Data channel write failed");
      data_.stop();
      in.close();
      return false;
    }
    delay(1);
  }

  data_.stop();
  in.close();

  int code = 0;
  String finalLine;
  if (!readReply(code, finalLine, 20000)) {
    Serial.println("[FTP] Missing final transfer reply");
    return false;
  }
  if (code != 226 && code != 250) {
    Serial.printf("[FTP] Transfer failed [%d]: %s\n", code, finalLine.c_str());
    return false;
  }

  return true;
}

bool FtpUploader::ensureSession() {
  if (!ctrl_.connected()) {
    if (!ctrl_.connect(host_.c_str(), port_)) {
      Serial.println("[FTP] Control channel connect failed");
      return false;
    }

    int code = 0;
    String line;
    if (!readReply(code, line, 10000) || code != 220) {
      Serial.printf("[FTP] Welcome failed [%d]: %s\n", code, line.c_str());
      ctrl_.stop();
      return false;
    }

    String userLine;
    if (!sendCommand("USER " + user_, 331, 230, &userLine, 10000)) {
      ctrl_.stop();
      return false;
    }

    if (userLine.startsWith("331")) {
      if (!sendCommand("PASS " + pass_, 230, -1, nullptr, 10000)) {
        ctrl_.stop();
        return false;
      }
    }

    if (!sendCommand("TYPE I", 200, -1, nullptr, 5000)) {
      ctrl_.stop();
      return false;
    }

    sendCommand("MKD " + remoteDir_, 257, 550, nullptr, 5000);

    if (!sendCommand("CWD " + remoteDir_, 250, -1, nullptr, 5000)) {
      ctrl_.stop();
      return false;
    }
  }

  return true;
}

bool FtpUploader::enterPassiveMode(String& ip, uint16_t& port) {
  String line;
  if (!sendCommand("PASV", 227, -1, &line, 10000)) {
    return false;
  }

  const int left = line.indexOf('(');
  const int right = line.indexOf(')', left + 1);
  if (left < 0 || right < 0 || right <= left) {
    Serial.printf("[FTP] PASV parse failed: %s\n", line.c_str());
    return false;
  }

  int h1 = 0;
  int h2 = 0;
  int h3 = 0;
  int h4 = 0;
  int p1 = 0;
  int p2 = 0;
  String tuple = line.substring(left + 1, right);
  if (sscanf(tuple.c_str(), "%d,%d,%d,%d,%d,%d", &h1, &h2, &h3, &h4, &p1, &p2) != 6) {
    Serial.printf("[FTP] PASV tuple invalid: %s\n", tuple.c_str());
    return false;
  }

  ip = String(h1) + "." + String(h2) + "." + String(h3) + "." + String(h4);
  port = static_cast<uint16_t>((p1 << 8) | p2);
  return true;
}

bool FtpUploader::sendCommand(const String& cmd,
                              int expectedA,
                              int expectedB,
                              String* outLine,
                              uint32_t timeoutMs) {
  ctrl_.print(cmd);
  ctrl_.print("\r\n");

  int code = 0;
  String line;
  if (!readReply(code, line, timeoutMs)) {
    Serial.printf("[FTP] Timeout waiting reply for: %s\n", cmd.c_str());
    return false;
  }

  if (outLine != nullptr) {
    *outLine = line;
  }

  if (code == expectedA || (expectedB >= 0 && code == expectedB)) {
    return true;
  }

  Serial.printf("[FTP] Unexpected [%d] for '%s': %s\n", code, cmd.c_str(), line.c_str());
  return false;
}

bool FtpUploader::readReply(int& code, String& line, uint32_t timeoutMs) {
  const uint32_t start = millis();
  String current;
  int multiCode = -1;

  while (millis() - start < timeoutMs) {
    while (ctrl_.available()) {
      const char c = static_cast<char>(ctrl_.read());
      if (c == '\r') {
        continue;
      }
      if (c == '\n') {
        if (current.length() == 0) {
          continue;
        }

        if (current.length() >= 3 && isDigit(current[0]) && isDigit(current[1]) && isDigit(current[2])) {
          const int parsed = (current[0] - '0') * 100 + (current[1] - '0') * 10 + (current[2] - '0');
          const bool isMultiline = current.length() > 3 && current[3] == '-';

          if (multiCode < 0) {
            multiCode = parsed;
          }

          if (!isMultiline && (multiCode < 0 || parsed == multiCode)) {
            code = parsed;
            line = current;
            return true;
          }
        }

        current = "";
        continue;
      }

      if (current.length() < 250) {
        current += c;
      }
    }

    delay(2);
  }

  return false;
}
