/* Minimal Mac app entry: clear Gatekeeper quarantine, then run the game. */
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <mach-o/dyld.h>

static int parent_dir(char *path) {
  char *slash = strrchr(path, '/');
  if (!slash || slash == path) {
    return -1;
  }
  *slash = '\0';
  return 0;
}

static void strip_quarantine(const char *app_bundle) {
  char cmd[PATH_MAX + 64];
  snprintf(cmd, sizeof(cmd), "/usr/bin/xattr -cr \"%s\" >/dev/null 2>&1", app_bundle);
  system(cmd);
}

int main(int argc, char **argv) {
  (void)argc;
  (void)argv;

  char exe[PATH_MAX];
  uint32_t size = sizeof(exe);
  if (_NSGetExecutablePath(exe, &size) != 0) {
    fprintf(stderr, "Crownfall: cannot resolve executable path\n");
    return 1;
  }

  char path[PATH_MAX];
  if (!realpath(exe, path)) {
    strncpy(path, exe, sizeof(path) - 1);
    path[sizeof(path) - 1] = '\0';
  }

  /* .../Crownfall.app/Contents/MacOS/Crownfall → app bundle */
  if (parent_dir(path) != 0 || parent_dir(path) != 0 || parent_dir(path) != 0) {
    fprintf(stderr, "Crownfall: bad app layout\n");
    return 1;
  }

  strip_quarantine(path);

  char script[PATH_MAX];
  snprintf(script, sizeof(script), "%s/Contents/Resources/run_crownfall.sh", path);
  if (access(script, X_OK) != 0) {
    fprintf(stderr, "Crownfall: missing launcher script at %s\n", script);
    return 1;
  }

  execl("/bin/bash", "bash", script, (char *)NULL);
  perror("Crownfall: failed to start");
  return 1;
}
