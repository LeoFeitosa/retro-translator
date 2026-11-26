/* Retro Translator: video memory and cartridge pointers for whoever loads the library (Windows has no symbol table) */
RETRO_API void *retro_memory_view(unsigned which)  /* retro_ prefix: link.T only exports those */
{
   switch (which)
   {
      case 0: return vram;
      case 1: return reg;
      case 2: return cram;
      case 3: return vsram;
      case 4: return cart.rom;  /* translation written into the ROM after the power-up checks */
      case 5: return &cart.romsize;
   }
   return NULL;
}
