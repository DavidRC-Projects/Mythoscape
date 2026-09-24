#!/usr/bin/env python3
"""
Visual verification script for building rendering fixes.

Displays the regenerated void_sanctum.png to verify:
1. Seamless wall connections (no gaps)
2. Recessed entrance carved INTO front wall
3. Visible building depth from side walls
4. One unified extruded volume

Usage: python3 verify_building_fix.py
"""
import os
import sys

try:
    import pygame
except ImportError:
    print("ERROR: pygame not installed")
    print("Install with: pip3 install pygame")
    sys.exit(1)

# Navigate to the buildings assets directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BUILDINGS_DIR = os.path.join(SCRIPT_DIR, "game", "assets", "mmorpg", "client", "assets", "buildings")
VOID_PNG = os.path.join(BUILDINGS_DIR, "void_sanctum.png")

if not os.path.exists(VOID_PNG):
    print(f"ERROR: void_sanctum.png not found at {VOID_PNG}")
    sys.exit(1)

pygame.init()

# Load the void sanctum image
try:
    img = pygame.image.load(VOID_PNG)
except pygame.error as e:
    print(f"ERROR loading void_sanctum.png: {e}")
    sys.exit(1)

w, h = img.get_size()
print(f"Loaded void_sanctum.png: {w}x{h} pixels")
print()
print("VERIFICATION CHECKLIST:")
print("======================")
print()
print("Look for these features in the displayed image:")
print()
print("✓ ONE CONTINUOUS VOLUME:")
print("  - Front wall and side wall connect seamlessly at their shared edge")
print("  - No visible black gap or seam between front and side walls")
print("  - Stone texture flows continuously around the corner")
print()
print("✓ VISIBLE DEPTH:")
print("  - Side wall (right side) extends backward from front wall")
print("  - Roof covers the full extruded volume (front + side depth)")
print("  - Foundation wraps around both front and side walls")
print()
print("✓ RECESSED ENTRANCE:")
print("  - Arched doorway is carved INTO the front wall (not a separate object)")
print("  - Visible inner edges (jambs) show wall thickness")
print("  - Dark throat/interior visible through the opening")
print("  - Door panel sits INSIDE the recess, not at the front surface")
print("  - Purple glow emanates from interior, not from a pasted sprite")
print()
print("✓ NO PASTED OBJECTS:")
print("  - No separate entrance sprite floating in front")
print("  - No visible outline or border around the entrance that doesn't match wall")
print("  - Entrance opening is part of the wall, not on top of it")
print()
print("Press ESC or close window to exit.")
print()

# Create display window
screen = pygame.display.set_mode((w + 40, h + 100))
pygame.display.set_caption("Mythoscape - Building Rendering Fix Verification")

# Create background
bg = pygame.Surface(screen.get_size())
bg.fill((20, 25, 30))

# Add title text
font = pygame.font.Font(None, 24)
title = font.render("Void Sanctum - Fixed Rendering", True, (200, 220, 240))
subtitle = font.render("Check for seamless walls, recessed entrance, visible depth", True, (150, 170, 190))

# Main loop
clock = pygame.time.Clock()
running = True

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                running = False
    
    screen.blit(bg, (0, 0))
    screen.blit(title, (20, 10))
    screen.blit(subtitle, (20, 35))
    screen.blit(img, (20, 70))
    
    pygame.display.flip()
    clock.tick(30)

pygame.quit()
print()
print("Verification complete!")
print()
print("If you observed all checkmarks above, the fix is working correctly.")
print("Buildings now render as unified extruded volumes with recessed entrances.")
