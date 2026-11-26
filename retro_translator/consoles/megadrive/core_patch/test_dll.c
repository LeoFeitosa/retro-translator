#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
struct gi { const char *path; const void *data; size_t size; const char *meta; };
static bool env(unsigned cmd, void *data) {
  if (cmd == 10) return true;            /* SET_PIXEL_FORMAT */
  if (cmd == 9 || cmd == 31) { *(const char **)data = "."; return true; } /* SYSTEM/SAVE dir */
  return false;
}
static void video(const void *d, unsigned w, unsigned h, size_t p) {}
static void aud(short l, short r) {}
static size_t audb(const short *d, size_t n) { return n; }
static void poll(void) {}
static short st(unsigned a, unsigned b, unsigned c, unsigned d) { return 0; }
int main(int argc, char **argv) {
  HMODULE h = LoadLibraryA(argv[1]);
  if (!h) { printf("LoadLibrary falhou %lu\n", GetLastError()); return 1; }
  typedef void (*fp_set)(void*); typedef void (*fp_v)(void); typedef bool (*fp_load)(struct gi*);
  typedef unsigned char *(*fp_mem)(unsigned);
  fp_set retro_set_environment = (fp_set)GetProcAddress(h, "retro_set_environment");
  fp_set retro_set_video_refresh = (fp_set)GetProcAddress(h, "retro_set_video_refresh");
  fp_set retro_set_audio_sample = (fp_set)GetProcAddress(h, "retro_set_audio_sample");
  fp_set retro_set_audio_sample_batch = (fp_set)GetProcAddress(h, "retro_set_audio_sample_batch");
  fp_set retro_set_input_poll = (fp_set)GetProcAddress(h, "retro_set_input_poll");
  fp_set retro_set_input_state = (fp_set)GetProcAddress(h, "retro_set_input_state");
  fp_v retro_init = (fp_v)GetProcAddress(h, "retro_init"); fp_v retro_run = (fp_v)GetProcAddress(h, "retro_run");
  fp_load retro_load_game = (fp_load)GetProcAddress(h, "retro_load_game");
  fp_mem retro_memory_view = (fp_mem)GetProcAddress(h, "retro_memory_view");
  if (!retro_memory_view) { puts("sem retro_memory_view"); return 1; }
  retro_set_environment((void*)env); retro_set_video_refresh((void*)video); retro_set_audio_sample((void*)aud);
  retro_set_audio_sample_batch((void*)audb); retro_set_input_poll((void*)poll); retro_set_input_state((void*)st);
  retro_init();
  FILE *f = fopen(argv[2], "rb"); fseek(f, 0, SEEK_END); long n = ftell(f); fseek(f, 0, SEEK_SET);
  void *buf = malloc(n); fread(buf, 1, n, f); fclose(f);
  struct gi g = { argv[2], buf, (size_t)n, NULL };
  if (!retro_load_game(&g)) { puts("ROM recusada"); return 1; }
  for (int i = 0; i < 600; i++) retro_run();
  unsigned char *v = retro_memory_view(0); long s = 0;
  for (int i = 0; i < 0x10000; i++) s += v[i];
  printf("ok vram_soma=%ld reg1=%02x\n", s, retro_memory_view(1)[1]);
  return 0;
}
