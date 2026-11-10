#include "cmCurl.h"
#include <cstdio>
#include <string>

int main(int argc, char **argv) {
  if (argc < 2) return 2;
  CURL *curl = curl_easy_init();
  if (!curl) return 2;
  std::string error = cmCurlSetCAInfo(curl, argc == 3 ? argv[2] : "");
  if (!error.empty()) {
    std::fprintf(stderr, "%s\n", error.c_str());
    return 2;
  }
  CURLcode result = curl_easy_setopt(curl, CURLOPT_URL, argv[1]);
  if (result == CURLE_OK) result = curl_easy_setopt(curl, CURLOPT_TIMEOUT, 10L);
  if (result == CURLE_OK) result = curl_easy_perform(curl);
  if (result != CURLE_OK) std::fprintf(stderr, "%s\n", curl_easy_strerror(result));
  curl_easy_cleanup(curl);
  return static_cast<int>(result);
}
