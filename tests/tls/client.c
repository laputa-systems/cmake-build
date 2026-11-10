#include <curl/curl.h>
#include <stdio.h>
#include <stdlib.h>

int main(int argc, char **argv) {
  if (argc < 2 || argc > 3) return 2;
  CURL *curl = curl_easy_init();
  if (!curl) return 2;
  const char *file = argc == 3 ? argv[2] : getenv("SSL_CERT_FILE");
  CURLcode result = curl_easy_setopt(curl, CURLOPT_URL, argv[1]);
  if (result == CURLE_OK) result = curl_easy_setopt(curl, CURLOPT_TIMEOUT, 10L);
  if (result == CURLE_OK && file)
    result = curl_easy_setopt(curl, CURLOPT_CAINFO, file);
  else if (result == CURLE_OK)
    result = curl_easy_setopt(curl, CURLOPT_SSL_OPTIONS, CURLSSLOPT_NATIVE_CA);
  if (result == CURLE_OK) result = curl_easy_perform(curl);
  if (result != CURLE_OK) fprintf(stderr, "%s\n", curl_easy_strerror(result));
  curl_easy_cleanup(curl);
  return (int)result;
}
