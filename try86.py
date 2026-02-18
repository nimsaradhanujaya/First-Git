#!/usr/bin/env python3

from rgbmatrix import RGBMatrix, RGBMatrixOptions
from esp32_wifi_manager import ESP32WiFiManager
import time
import sys
import random
import termios
import tty
import select
import os
import math
import RPi.GPIO as GPIO

class MultiplexerRemote:
    def __init__(self):
        # GPIO pin mappings (BCM numbering)
        self.M1_PINS = {
            'EN': None,  # Tie to GND permanently
            'S0': 26,
            'S1': 19,
            'S2': 13,
            'S3': 6,
            'SIG': 5
        }
        
        self.M2_PINS = {
            'EN': None,  # Tie to GND permanently
            'S0': 14,
            'S1': 12,
            'S2': 21,
            'S3': 20,
            'SIG': 16
        }
        
        # Button channel mappings
        self.REMOTE_CHANNELS = {
            'remote1': {'up': 0, 'right': 1, 'down': 2, 'left': 3, 'select': 4},
            'remote2': {'up': 8, 'right': 9, 'down': 10, 'left': 11, 'select': 12}
        }
        
        # Player mapping to remotes
        self.PLAYER_REMOTE_MAP = {
            0: ('M1', 'remote1'),  # Player 1 -> M1 Remote1
            1: ('M2', 'remote1'),  # Player 2 -> M2 Remote1
            2: ('M1', 'remote2'),  # Player 3 -> M1 Remote2
            3: ('M2', 'remote2')   # Player 4 -> M2 Remote2
        }
        
        self.setup_gpio()
        # Button state tracking for debouncing
        self.button_states = {}
        self.last_button_time = {}
        self.button_debounce = 0.2  # 200ms debounce

    def setup_gpio(self):
        """Initialize GPIO settings"""
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)
        
        # Setup M1 pins
        GPIO.setup(self.M1_PINS['S0'], GPIO.OUT)
        GPIO.setup(self.M1_PINS['S1'], GPIO.OUT)
        GPIO.setup(self.M1_PINS['S2'], GPIO.OUT)
        GPIO.setup(self.M1_PINS['S3'], GPIO.OUT)
        GPIO.setup(self.M1_PINS['SIG'], GPIO.IN, pull_up_down=GPIO.PUD_UP)
        
        # Setup M2 pins
        GPIO.setup(self.M2_PINS['S0'], GPIO.OUT)
        GPIO.setup(self.M2_PINS['S1'], GPIO.OUT)
        GPIO.setup(self.M2_PINS['S2'], GPIO.OUT)
        GPIO.setup(self.M2_PINS['S3'], GPIO.OUT)
        GPIO.setup(self.M2_PINS['SIG'], GPIO.IN, pull_up_down=GPIO.PUD_UP)

    def select_channel(self, mux_pins, channel):
        """Select specific channel on multiplexer"""
        GPIO.output(mux_pins['S0'], channel & 0x01)
        GPIO.output(mux_pins['S1'], (channel >> 1) & 0x01)
        GPIO.output(mux_pins['S2'], (channel >> 2) & 0x01)
        GPIO.output(mux_pins['S3'], (channel >> 3) & 0x01)

    def read_button(self, mux_pins, channel):
        """Read a specific button with debouncing"""
        self.select_channel(mux_pins, channel)
        time.sleep(0.001)  # Small delay for channel selection
        # Read button state (pressed = LOW)
        return not GPIO.input(mux_pins['SIG'])

    def get_player_input(self, player):
        """Get input from specific player's remote with debouncing"""
        if player not in self.PLAYER_REMOTE_MAP:
            return None
            
        mux_name, remote_name = self.PLAYER_REMOTE_MAP[player]
        mux_pins = self.M1_PINS if mux_name == 'M1' else self.M2_PINS
        current_time = time.time()
        pressed_buttons = []
        
        for button_name, channel in self.REMOTE_CHANNELS[remote_name].items():
            button_key = f"{player}_{button_name}"
            
            # Check if button is pressed
            if self.read_button(mux_pins, channel):
                # Check debouncing
                if (button_key not in self.last_button_time or 
                    current_time - self.last_button_time[button_key] > self.button_debounce):
                    pressed_buttons.append(button_name)
                    self.last_button_time[button_key] = current_time
        
        return pressed_buttons[0] if pressed_buttons else None

    def cleanup(self):
        """Clean up GPIO resources"""
        GPIO.cleanup()

# Matrix configuration with optimized settings for minimal flickering
options = RGBMatrixOptions()
options.rows = 64
options.cols = 64
options.chain_length = 5  # 4 players + 1 main display
options.parallel = 1
options.hardware_mapping = 'regular'
options.gpio_slowdown = 4  # Critical for reducing flickering
options.brightness = 80
options.pwm_bits = 11
options.pwm_lsb_nanoseconds = 130
options.led_rgb_sequence = "RGB"
options.drop_privileges = False
options.limit_refresh_rate_hz = 60  # Capped refresh rate
options.disable_hardware_pulsing = True  # Essential for flicker reduction

matrix = RGBMatrix(options=options)

# Color definitions
BLACK = (0, 0, 0)
RED = (255, 0, 0)
WHITE = (255, 255, 255)
YELLOW = (255, 255, 0)
BLUE = (0, 0, 255)
GREEN = (0, 255, 0)
CYAN = (0, 255, 255)
MAGENTA = (255, 0, 255)
ORANGE = (255, 165, 0)
PURPLE = (128, 0, 128)
LIGHT_BLUE = (173, 216, 230)
PINK = (255, 192, 203)
LIGHT_GREEN = (144, 238, 144)

# Game constants
CARD_WIDTH = 16
CARD_HEIGHT = 32
PANEL_WIDTH = 64
PANEL_HEIGHT = 64
PANEL_COUNT = 5

# Card positions for player panels
CARD_POSITIONS = [
    (0, 0), (16, 0), (32, 0), (48, 0),
    (0, 32), (16, 32), (32, 32), (48, 32)
]

# Main panel positions - circular layout with better spacing
MAIN_PANEL_POSITIONS = [
    (24, 2),   # Player 1 - Top
    (46, 16),  # Player 2 - Right  
    (24, 32),  # Player 3 - Bottom
    (2, 16)    # Player 4 - Left
]

# Teams: Team A (Players 1,3), Team B (Players 2,4)
TEAMS = {'A': [0, 2], 'B': [1, 3]}

# Suits and ranks - Updated for Omi (A-K-Q-J-10-9-8-7)
SUITS = ['hearts', 'diamonds', 'clubs', 'spades']
SUIT_COLORS = {'hearts': RED, 'diamonds': RED, 'clubs': WHITE, 'spades': WHITE}
RANKS = ['A', 'K', 'Q', 'J', '10', '9', '8', '7']  # Updated for Omi
RANK_VALUES = {'A': 14, 'K': 13, 'Q': 12, 'J': 11, '10': 10, '9': 9, '8': 8, '7': 7}  # Updated for Omi

# Double buffering system with dirty flags
class PanelBuffer:
    def __init__(self):
        self.front_buffer = [[BLACK for _ in range(PANEL_WIDTH)] for _ in range(PANEL_HEIGHT)]
        self.back_buffer = [[BLACK for _ in range(PANEL_WIDTH)] for _ in range(PANEL_HEIGHT)]
        self.dirty = False

    def swap(self):
        self.front_buffer, self.back_buffer = self.back_buffer, self.front_buffer
        self.dirty = False

    def clear_back(self):
        for y in range(PANEL_HEIGHT):
            for x in range(PANEL_WIDTH):
                self.back_buffer[y][x] = BLACK

# Create buffers for each panel
panel_buffers = [PanelBuffer() for _ in range(PANEL_COUNT)]

def commit_buffers():
    """Commit all buffers to the matrix at once"""
    for panel_num in range(PANEL_COUNT):
        if panel_buffers[panel_num].dirty:
            x_offset = panel_num * PANEL_WIDTH
            buffer = panel_buffers[panel_num].front_buffer
            
            for y in range(PANEL_HEIGHT):
                for x in range(PANEL_WIDTH):
                    matrix.SetPixel(x_offset + x, y, *buffer[y][x])
            
            panel_buffers[panel_num].swap()

def clear_panel(panel_num):
    """Clear a specific panel's back buffer"""
    panel_buffers[panel_num].clear_back()
    panel_buffers[panel_num].dirty = True

def clear_all_panels():
    """Clear all panels' back buffers"""
    for i in range(PANEL_COUNT):
        clear_panel(i)

def start_new_round():
    """Start a new round with proper trump selector (dealer's right)"""
    global hands, game_state, panel_buffers
    
    # Deal cards
    deck = create_deck()  
    hands = deal_cards(deck)
    
    # Set trump selector to dealer's RIGHT (anticlockwise)
    game_state['trump_selector'] = (game_state['dealer'] + 1) % 4
    game_state['phase'] = 'trump_selection'
    game_state['trump_suit'] = None
    game_state['trump_team'] = None
    game_state['current_trick'] = [None, None, None, None]
    game_state['tricks_won'] = [0, 0, 0, 0]
    game_state['active_players'] = [True, True, True, True]
    game_state['half_court_mode'] = False
    game_state['full_court_mode'] = False
    game_state['half_court_player'] = None
    game_state['full_court_player'] = None
    game_state['first_trick_started'] = False
    game_state['trick_leader'] = None
    
    # Display trump selection prompt with enhanced text
    clear_panel(4)
    draw_perfect_text(4, f"PLAYER {game_state['trump_selector'] + 1}", YELLOW, 10)
    draw_perfect_text(4, "SELECT TRUMP", WHITE, 20)
    panel_buffers[4].dirty = True
    commit_buffers()
    
    print(f"Round {game_state['round_number']}: Player {game_state['trump_selector'] + 1} selects trump")

def create_deck():
    """Create a standard deck for Omi card game (A-K-Q-J-10-9-8-7 in all suits)"""
    deck = []
    for suit in SUITS:
        for rank in RANKS:
            deck.append((suit, rank))
    return deck

def deal_cards(deck):
    """Deal 8 cards to each of 4 players"""
    random.shuffle(deck)
    hands = [[], [], [], []]
    
    # Deal 8 cards to each player
    for i in range(8):
        for player in range(4):
            if i * 4 + player < len(deck):
                hands[player].append(deck[i * 4 + player])
    
    return hands

def setup_first_trick():
    """Ensure trump selector leads first trick in ALL game modes"""
    if not game_state.get('first_trick_started', False):
        # Trump selector ALWAYS leads first trick (rule compliance)
        trump_selector = game_state['trump_selector']
        game_state['trick_leader'] = trump_selector
        game_state['first_trick_started'] = True
        
        print(f"FIRST TRICK: Player {trump_selector + 1} (trump selector) leads")
        
        # Clear main panel and show first trick leader
        clear_panel(4)
        draw_text_enhanced_fixed(4, f"Player {trump_selector + 1}", YELLOW, PANEL_WIDTH // 2, 10, center=True)
        draw_text_enhanced_fixed(4, "Leads First", WHITE, PANEL_WIDTH // 2, 20, center=True)
        draw_text_enhanced_fixed(4, "Trick", WHITE, PANEL_WIDTH // 2, 30, center=True)
        panel_buffers[4].dirty = True
        commit_buffers()
        time.sleep(2)
        
        return trump_selector

# Enhanced suit symbols - larger and more detailed
symbols = {
    'hearts': [
        "0000000000000000",
        "0001100001100000",
        "0011110011110000",
        "0111111111110000",
        "0111111111110000",
        "0111111111110000",
        "0011111111100000",
        "0001111111000000",
        "0000111110000000",
        "0000011100000000",
        "0000001000000000",
        "0000000000000000",
        "0000000000000000",
        "0000000000000000",
        "0000000000000000",
        "0000000000000000"
    ],
    'diamonds': [
        "0000000000000000",
        "0000001000000000",
        "0000011100000000",
        "0000111110000000",
        "0001111111000000",
        "0011111111100000",
        "0111111111110000",
        "0011111111100000",
        "0001111111000000",
        "0000111110000000",
        "0000011100000000",
        "0000001000000000",
        "0000000000000000",
        "0000000000000000",
        "0000000000000000",
        "0000000000000000"
    ],
    'clubs': [
        "0000000000000000",
        "0000011000000000",
        "0000111100000000",
        "0000111100000000",
        "0001100110000000",
        "0011111111000000",
        "0011111111000000",
        "0001111110000000",
        "0000111100000000",
        "0000011000000000",
        "0000111100000000",
        "0001111110000000",
        "0000000000000000",
        "0000000000000000",
        "0000000000000000",
        "0000000000000000"
    ],
    'spades': [
        "0000000000000000",
        "0000001000000000",
        "0000011100000000",
        "0000111110000000",
        "0001111111000000",
        "0011111111100000",
        "0111111111110000",
        "0111111111110000",
        "0001101101000000",
        "0000111110000000",
        "0000011100000000",
        "0000111110000000",
        "0000000000000000",
        "0000000000000000",
        "0000000000000000",
        "0000000000000000"
    ]
}

# Enhanced rank patterns with better spacing
rank_patterns = {
    'A': [
        "0000000000000000",
        "0000011000000000",
        "0000111100000000",
        "0001110110000000",
        "0011100011000000",
        "0111000011100000",
        "0110000001100000",
        "0111111111100000",
        "0110000001100000",
        "0110000001100000",
        "0110000001100000",
        "0000000000000000"
    ],
    'K': [
        "0000000000000000",
        "0110000011000000",
        "0110000110000000",
        "0110001100000000",
        "0110011000000000",
        "0111110000000000",
        "0111110000000000",
        "0110011000000000",
        "0110001100000000",
        "0110000110000000",
        "0110000011000000",
        "0000000000000000"
    ],
    'Q': [
        "0000000000000000",
        "0001111100000000",
        "0011000110000000",
        "0110000011000000",
        "0110000011000000",
        "0110000011000000",
        "0110000011000000",
        "0110001011000000",
        "0110011011000000",
        "0011000110000000",
        "0001111101000000",
        "0000000000000000"
    ],
    'J': [
        "0000000000000000",
        "0000111100000000",
        "0000011000000000",
        "0000011000000000",
        "0000011000000000",
        "0000011000000000",
        "0000011000000000",
        "0000011000000000",
        "0100011000000000",
        "0110011000000000",
        "0011110000000000",
        "0000000000000000"
    ],
    '10': [
        "0000000000000000",
        "0100001110000000",
        "0110010001000000",
        "0110010001000000",
        "0110010001000000",
        "0110010001000000",
        "0110010001000000",
        "0110010001000000",
        "0110010001000000",
        "0110010001000000",
        "0100001110000000",
        "0000000000000000"
    ],
    '9': [
        "0000000000000000",
        "0001111000000000",
        "0011001100000000",
        "0110000110000000",
        "0110000110000000",
        "0110000110000000",
        "0011001110000000",
        "0001111110000000",
        "0000000110000000",
        "0000001100000000",
        "0001111000000000",
        "0000000000000000"
    ],
    '8': [
        "0000000000000000",
        "0001111000000000",
        "0011001100000000",
        "0110000110000000",
        "0110000110000000",
        "0011111100000000",
        "0110000110000000",
        "0110000110000000",
        "0110000110000000",
        "0011001100000000",
        "0001111000000000",
        "0000000000000000"
    ],
    '7': [
        "0000000000000000",
        "0111111110000000",
        "0000000110000000",
        "0000001100000000",
        "0000011000000000",
        "0000110000000000",
        "0001100000000000",
        "0011000000000000",
        "0110000000000000",
        "0110000000000000",
        "0110000000000000",
        "0000000000000000"
    ]
}

def get_perfect_letter_pattern(letter):
    """Get pixel pattern for letters with PERFECT spacing and readability"""
    patterns = {
        'W': [
            "11000000000011",
            "11000000000011", 
            "11000001000011",
            "11000011100011",
            "11000111110011",
            "11001111111011",
            "11011111111011",
            "01111000111110"
        ],
        'E': [
            "11111111111111",
            "11000000000000",
            "11000000000000", 
            "11111111110000",
            "11111111110000",
            "11000000000000",
            "11000000000000",
            "11111111111111"
        ],
        'L': [
            "11000000000000",
            "11000000000000",
            "11000000000000",
            "11000000000000", 
            "11000000000000",
            "11000000000000",
            "11000000000000",
            "11111111111111"
        ],
        'C': [
            "00111111111100",
            "01111111111110",
            "11110000000000",
            "11110000000000",
            "11110000000000",
            "11110000000000", 
            "01111111111110",
            "00111111111100"
        ],
        'O': [
            "00111111111100",
            "01111111111110", 
            "11110000001111",
            "11110000001111",
            "11110000001111",
            "11110000001111",
            "01111111111110",
            "00111111111100"
        ],
        'M': [
            "11000000000011",
            "11100000000111",
            "11111000001111", 
            "11111110111111",
            "11001111111011",
            "11000111110011",
            "11000001000011",
            "11000000000011"
        ],
        'D': [
            "11111111110000",
            "11000000011100",
            "11000000001110",
            "11000000001111",
            "11000000001111", 
            "11000000001110",
            "11000000011100",
            "11111111110000"
        ],
        'R': [
            "11111111111000",
            "11000000001110",
            "11000000001111",
            "11111111111000",
            "11111111100000",
            "11000111100000",
            "11000001110000", 
            "11000000111100"
        ],
        'A': [
            "00111111111000",
            "01111111111100",
            "11110000001111",
            "11110000001111",
            "11111111111111",
            "11111111111111",
            "11110000001111",
            "11110000001111"
        ],
        'T': [
            "11111111111111",
            "11111111111111",
            "00001111000000",
            "00001111000000",
            "00001111000000", 
            "00001111000000",
            "00001111000000",
            "00001111000000"
        ],
        'I': [
            "11111111111111",
            "11111111111111",
            "00001111000000",
            "00001111000000",
            "00001111000000",
            "00001111000000",
            "11111111111111",
            "11111111111111"
        ],
        'S': [
            "00111111111100",
            "01111111111110",
            "11110000000000",
            "01111111111000",
            "00001111111110",
            "00000000001111",
            "01111111111110",
            "00111111111100"
        ],
        'G': [
            "00111111111100",
            "01111111111110",
            "11110000000000",
            "11110011111111",
            "11110000001111",
            "11110000001111",
            "01111111111110", 
            "00111111111100"
        ],
        'N': [
            "11110000001111",
            "11111000001111", 
            "11111100001111",
            "11111110001111",
            "11110111001111",
            "11110011101111",
            "11110001111111",
            "11110000111111"
        ],
        'B': [
            "11111111111000",
            "11000000001110",
            "11000000001111",
            "11111111111000",
            "11111111111000",
            "11000000001111",
            "11000000001110",
            "11111111111000"
        ],
        'H': [
            "11110000001111",
            "11110000001111",
            "11110000001111",
            "11111111111111",
            "11111111111111",
            "11110000001111",
            "11110000001111",
            "11110000001111"
        ],
        'U': [
            "11110000001111",
            "11110000001111", 
            "11110000001111",
            "11110000001111",
            "11110000001111",
            "11110000001111",
            "01111111111110",
            "00111111111100"
        ],
        'P': [
            "11111111111000",
            "11000000001110",
            "11000000001111",
            "11000000001110",
            "11111111111000",
            "11110000000000",
            "11110000000000",
            "11110000000000"
        ],
        'V': [
            "11110000001111",
            "11110000001111",
            "11110000001111",
            "01111000011110",
            "01111000011110",
            "00111100111100",
            "00011111111000",
            "00001111110000"
        ],
        'Y': [
            "11110000001111",
            "11110000001111",
            "01111000011110",
            "00111100111100",
            "00011111111000",
            "00001111110000",
            "00001111110000",
            "00001111110000"
        ],
        'F': [
            "11111111111111",
            "11110000000000",
            "11110000000000",
            "11111111110000",
            "11111111110000",
            "11110000000000",
            "11110000000000",
            "11110000000000"
        ],
        'K': [
            "11110000001111",
            "11110000011110",
            "11110000111100",
            "11110001111000",
            "11111111110000",
            "11110001111000",
            "11110000111100",
            "11110000011111"
        ],
        'Q': [
            "00111111111100",
            "01111111111110",
            "11110000001111",
            "11110000001111",
            "11110110001111",
            "11110011001111",
            "01111111111110",
            "00111111111111"
        ],
        'J': [
            "00001111111111",
            "00000000111100",
            "00000000111100",
            "00000000111100",
            "11110000111100",
            "11110000111100",
            "01111111111100",
            "00111111110000"  
        ],
        'Z': [
            "11111111111111",
            "00000000011110",
            "00000000111100",
            "00000001111000",
            "00000111100000",
            "00001111000000",
            "00111100000000",
            "11111111111111"
        ],
        '1': [
            "00001111000000",
            "00011111000000",
            "00111111000000",
            "00001111000000",
            "00001111000000",
            "00001111000000",
            "00001111000000",
            "11111111111111"
        ],
        '2': [
            "00111111111100",
            "01111111111110",
            "00000000001111",
            "00000000111110",
            "00001111111100",
            "00111111000000",
            "01111100000000",
            "11111111111111"
        ],
        '3': [
            "00111111111100",
            "01111111111110",
            "00000000001111",
            "00011111111110",
            "00011111111110",
            "00000000001111",
            "01111111111110",
            "00111111111100"
        ],
        '4': [
            "00000000011110",
            "00000000111110",
            "00000001111110",
            "00000111111110",
            "00011111011110",
            "11111111111111",
            "00000000011110",
            "00000000011110"
        ],
        '0': [
            "00111111111100",
            "01111111111110",
            "11110011001111",
            "11110110101111", 
            "11111010011111",
            "11111001101111",
            "01111111111110",
            "00111111111100"
        ],
        ' ': [
            "00000000000000",
            "00000000000000",
            "00000000000000",
            "00000000000000",
            "00000000000000",
            "00000000000000",
            "00000000000000",
            "00000000000000"
        ]
    }
    return patterns.get(letter, patterns[' '])

# Global game state - Updated with half court support
game_state = {
    'trump_suit': None,
    'trump_selector': None,
    'trump_team': None,
    'current_trick': [],
    'trick_leader': None,
    'trick_lead_suit': None,
    'team_tokens': {'A': 10, 'B': 10},
    'team_scores': {'A': 0, 'B': 0},
    'tricks_won': {'A': 0, 'B': 0},
    'current_round': 1,
    'phase': 'welcome',
    'pending_tokens': 0,
    'animation_frame': 0,
    'progress': 0,
    'last_update': 0,
    'trick_display_start': 0,
    'trick_cards_displayed': False,
    'dealer': 0,
    'kapothi_announced': False,
    'kapothi_announcer': None,
    'tricks_played': 0,
    # Half court new variables
    'half_court_mode': False,
    'half_court_player': None,
    'half_court_team': None,
    'half_court_option_time': 0,
    'half_court_selection': 0, # 0=YES, 1=NO
    'active_players': [0, 1, 2, 3], # Which players are active in current game
    'first_four_cards_dealt': False,
    'display_mode': 'normal', # Controls what gets displayed
    'first_four_display': [], # Stores first 4 cards for each player
    'half_court_timer': 0, # Timer for half court option
    'full_court_mode' : False,
    'full_court_player' : None,
    'full_court_team' : None,
    'awaiting_full_court_decision' : False,
    'full_court_confirmation' : False,
    'full_court_tricks_won' : 0,
    'full_court_selection' : 0, # 0 = YES, 1 = NO,
    'wifi_manager': None,
    'esp32_ip': None,
    'scanning_active': False,
    'scan_team': None,
    'scans_required': 0,
    'scans_completed': 0,
    'show_scan_ready': False,
    'scan_ready_timer': 0,
    'show_scans_left': False,
    'scans_left_timer': 0,
    'team_tokens': {'A': 10, 'B': 10},
    'connection_status': 'disconnected',
    'arrow_blink_timer': 0,
    'arrow_blink_state': True,
    'last_arrow_update': time.time()
}

card_patterns = {}

def create_card_pattern(suit, rank):
    """Create and cache card patterns to minimize redraws"""
    if (suit, rank) in card_patterns:
        return card_patterns[(suit, rank)]
    
    pattern = [[BLACK for _ in range(CARD_WIDTH)] for _ in range(CARD_HEIGHT)]
    color = SUIT_COLORS[suit]
    
    # Add suit symbol
    symbol_data = symbols[suit]
    for y, row in enumerate(symbol_data[:12]):
        for x, pixel in enumerate(row[:16]):
            if pixel == '1':
                pattern[y + 2][x] = color
    
    # Add rank
    rank_data = rank_patterns[rank]
    for y, row in enumerate(rank_data):
        for x, pixel in enumerate(row[:16]):
            if pixel == '1':
                pattern[y + 18][x] = color
    
    card_patterns[(suit, rank)] = pattern
    return pattern

def draw_card(panel_num, pos_x, pos_y, card, selected=False):
    """Enhanced card drawing with clean selection border"""
    buffer = panel_buffers[panel_num].back_buffer
    pattern = create_card_pattern(card[0], card[1])
    
    # Draw card body
    for y in range(CARD_HEIGHT):
        for x in range(CARD_WIDTH):
            px, py = pos_x + x, pos_y + y
            if 0 <= px < PANEL_WIDTH and 0 <= py < PANEL_HEIGHT:
                if pattern[y][x] != BLACK:
                    buffer[py][px] = pattern[y][x]
                else:
                    buffer[py][px] = BLACK
    
    # Clean selection border - only the border, no extra lines
    if selected:
        border_color = YELLOW
        
        # Draw only the border lines
        for i in range(CARD_WIDTH):
            px = pos_x + i
            if 0 <= px < PANEL_WIDTH:
                if 0 <= pos_y < PANEL_HEIGHT:
                    buffer[pos_y][px] = border_color
                if 0 <= pos_y + CARD_HEIGHT - 1 < PANEL_HEIGHT:
                    buffer[pos_y + CARD_HEIGHT - 1][px] = border_color
        
        for i in range(CARD_HEIGHT):
            py = pos_y + i
            if 0 <= py < PANEL_HEIGHT:
                if 0 <= pos_x < PANEL_WIDTH:
                    buffer[py][pos_x] = border_color
                if 0 <= pos_x + CARD_WIDTH - 1 < PANEL_WIDTH:
                    buffer[py][pos_x + CARD_WIDTH - 1] = border_color
    
    panel_buffers[panel_num].dirty = True

def draw_player_arrow_indicator(panel_num, active_player, blink_state):
    """Draw properly shaped arrow indicators with perpendicular head-to-tail connection"""
    if not blink_state:
        return  # Don't draw when blinking off
    
    # All arrows are 11x11 pixels with proper arrow shape
    arrow_down = [
    [0,0,0,0,0,1,0,0,0,0,0],
    [0,0,0,0,0,1,0,0,0,0,0],
    [0,0,0,0,0,1,0,0,0,0,0],
    [0,0,0,0,0,1,0,0,0,0,0],
    [0,0,0,0,0,1,0,0,0,0,0],
    [0,0,0,0,0,1,0,0,0,0,0],  # Shaft
    [0,1,1,1,1,1,1,1,1,1,0],
    [0,0,1,1,1,1,1,1,1,0,0],
    [0,0,0,1,1,1,1,1,0,0,0],
    [0,0,0,0,1,1,1,0,0,0,0],
    [0,0,0,0,0,1,0,0,0,0,0]
]
    arrow_up = [
    [0,0,0,0,0,1,0,0,0,0,0],
    [0,0,0,0,1,1,1,0,0,0,0],
    [0,0,0,1,1,1,1,1,0,0,0],
    [0,0,1,1,1,1,1,1,1,0,0],
    [0,1,1,1,1,1,1,1,1,1,0],
    [0,0,0,0,0,1,0,0,0,0,0],  # Tip
    [0,0,0,0,0,1,0,0,0,0,0],
    [0,0,0,0,0,1,0,0,0,0,0],
    [0,0,0,0,0,1,0,0,0,0,0],
    [0,0,0,0,0,1,0,0,0,0,0],
    [0,0,0,0,0,1,0,0,0,0,0]
]
    arrow_right = [
    [0,0,0,0,0,1,0,0,0,0,0],
    [0,0,0,0,0,1,1,0,0,0,0],
    [0,0,0,0,0,1,1,1,0,0,0],
    [0,0,0,0,0,1,1,1,1,0,0],
    [0,0,0,0,0,1,1,1,1,1,0],
    [1,1,1,1,1,1,1,1,1,1,1],  # Shaft
    [0,0,0,0,0,1,1,1,1,1,0],
    [0,0,0,0,0,1,1,1,1,0,0],
    [0,0,0,0,0,1,1,1,0,0,0],
    [0,0,0,0,0,1,1,0,0,0,0],
    [0,0,0,0,0,1,0,0,0,0,0]
]
    arrow_left = [
    [0,0,0,0,0,1,0,0,0,0,0],
    [0,0,0,0,1,1,0,0,0,0,0],
    [0,0,0,1,1,1,0,0,0,0,0],
    [0,0,1,1,1,1,0,0,0,0,0],
    [0,1,1,1,1,1,0,0,0,0,0],
    [1,1,1,1,1,1,1,1,1,1,1],  # Shaft
    [0,1,1,1,1,1,0,0,0,0,0],
    [0,0,1,1,1,1,0,0,0,0,0],
    [0,0,0,1,1,1,0,0,0,0,0],
    [0,0,0,0,1,1,0,0,0,0,0],
    [0,0,0,0,0,1,0,0,0,0,0]
]

    # Optimized positions for 11x11 arrows
    arrow_positions = {
        0: (26, 52),   # Player 1 - Top (64-11-1 = 52, center: 26)
        1: (52, 26),  # Player 2 - Right (64-11-1 = 52)  
        2: (26, 1),  # Player 3 - Bottom (64-11-1 = 52, center: 26)
        3: (1, 26)    # Player 4 - Left (center: 26)
    }
    
    # Select arrow pattern and position
    patterns = {0: arrow_down, 1: arrow_right, 2: arrow_up, 3: arrow_left}
    
    if active_player not in patterns:
        return
    
    pattern = patterns[active_player]
    arrow_x, arrow_y = arrow_positions[active_player]
    
    # Arrow color - bright yellow for visibility
    arrow_color = YELLOW
    
    # Draw the arrow with bounds checking
    buffer = panel_buffers[panel_num].back_buffer
    for y, row in enumerate(pattern):
        for x, pixel in enumerate(row):
            if pixel == 1:
                px = arrow_x + x
                py = arrow_y + y
                if 0 <= px < PANEL_WIDTH and 0 <= py < PANEL_HEIGHT:
                    buffer[py][px] = arrow_color
    
    panel_buffers[panel_num].dirty = True


def draw_small_number(panel_num, number, color, x, y):
    """Draw a small number at specified position"""
    buffer = panel_buffers[panel_num].back_buffer
    
    # Simple 3x5 number patterns
    number_patterns = {
        0: ["111", "101", "101", "101", "111"],
        1: ["010", "110", "010", "010", "111"],
        2: ["111", "001", "111", "100", "111"],
        3: ["111", "001", "111", "001", "111"],
        4: ["101", "101", "111", "001", "001"],
        5: ["111", "100", "111", "001", "111"],
        6: ["111", "100", "111", "101", "111"],
        7: ["111", "001", "010", "100", "100"],
        8: ["111", "101", "111", "101", "111"],
        9: ["111", "101", "111", "001", "111"]
    }
    
    if number in number_patterns:
        pattern = number_patterns[number]
        for py, row in enumerate(pattern):
            for px, pixel in enumerate(row):
                if pixel == '1':
                    if 0 <= x + px < PANEL_WIDTH and 0 <= y + py < PANEL_HEIGHT:
                        buffer[y + py][x + px] = color
    
    panel_buffers[panel_num].dirty = True

def draw_horizontal_card_with_rotation(panel_num, card, position):
    """Draw a card horizontally with symbol and rank side by side, rotated for each player's readability"""
    if card is None:
        return
    
    buffer = panel_buffers[panel_num].back_buffer
    suit, rank = card
    color = SUIT_COLORS[suit]
    
    symbol_data = symbols[suit]
    rank_data = rank_patterns[rank]
    
    # Central square position and size
    square_size = 24
    central_x = (PANEL_WIDTH - square_size) // 2
    central_y = (PANEL_HEIGHT - square_size) // 2
    
    # ENLARGED dimensions for better visibility
    symbol_width = 14  # Increased from 12
    symbol_height = 14  # Increased from 12
    rank_width = 14    # Increased from 12
    rank_height = 14   # Increased from 12
    gap = 3           # Increased gap
    
    # Total card dimensions
    card_width = symbol_width + gap + rank_width
    card_height = max(symbol_height, rank_height)
    
    # IMPROVED positioning with ALL cards closer to center - SWAPPED TOP AND BOTTOM
    if position == 0:  # Top strip - Player 1 (NOW SHOWS AT BOTTOM with 0 degree rotation)
        start_x = central_x + (square_size - card_width) // 2
        start_y = central_y + square_size + 3  # MOVED CLOSER: reduced clearance from 10 to 3
        rotation = 0  # Bottom card has 0 degree rotation
    elif position == 1:  # Right strip - Player 2 (90 degree rotation)
        start_x = central_x + square_size + 6  # Already closer to center
        start_y = central_y + (square_size - card_width) // 2
        rotation = 90
    elif position == 2:  # Bottom strip - Player 3 (NOW SHOWS AT TOP with 180 degree rotation)
        start_x = central_x + (square_size - card_width) // 2
        start_y = central_y - card_height - 3  # MOVED CLOSER: reduced clearance from 10 to 3
        rotation = 180
    else:  # Left strip - Player 4 (270 degree rotation)
        start_x = central_x - card_height - 6  # Already closer to center
        start_y = central_y + (square_size - card_width) // 2
        rotation = 270
    
    # Draw symbol first
    symbol_start_x = start_x
    symbol_start_y = start_y + (card_height - symbol_height) // 2
    
    for y in range(min(len(symbol_data), 16)):  # Use more of the symbol data
        row = symbol_data[y]
        for x in range(min(len(row), 16)):
            if row[x] == '1':
                # Calculate original position
                orig_x = symbol_start_x + x
                orig_y = symbol_start_y + y
                
                # Apply CORRECTED rotation
                if rotation == 0:
                    final_x, final_y = orig_x, orig_y
                elif rotation == 90:
                    # Rotate 90 degrees clockwise around start point
                    rel_x = orig_x - start_x
                    rel_y = orig_y - start_y
                    final_x = start_x + rel_y
                    final_y = start_y + (card_width - 1 - rel_x)
                elif rotation == 180:
                    # Rotate 180 degrees
                    rel_x = orig_x - start_x
                    rel_y = orig_y - start_y
                    final_x = start_x + (card_width - 1 - rel_x)
                    final_y = start_y + (card_height - 1 - rel_y)
                else:  # rotation == 270
                    # Rotate 270 degrees clockwise (90 counter-clockwise)
                    rel_x = orig_x - start_x
                    rel_y = orig_y - start_y
                    final_x = start_x + (card_height - 1 - rel_y)
                    final_y = start_y + rel_x
                
                # Draw pixel with bounds checking
                if 0 <= final_x < PANEL_WIDTH and 0 <= final_y < PANEL_HEIGHT:
                    buffer[final_y][final_x] = color
    
    # Draw rank next to symbol with PROPER COLOR
    rank_start_x = start_x + symbol_width + gap
    rank_start_y = start_y + (card_height - rank_height) // 2
    
    # FIXED: Use red color for red suits, white for black suits
    rank_color = color if suit in ['hearts', 'diamonds'] else WHITE
    
    for y in range(min(len(rank_data), 16)):  # Use more of the rank data
        row = rank_data[y]
        for x in range(min(len(row), 16)):
            if row[x] == '1':
                # Calculate original position
                orig_x = rank_start_x + x
                orig_y = rank_start_y + y
                
                # Apply CORRECTED rotation (same logic as symbol)
                if rotation == 0:
                    final_x, final_y = orig_x, orig_y
                elif rotation == 90:
                    rel_x = orig_x - start_x
                    rel_y = orig_y - start_y
                    final_x = start_x + rel_y
                    final_y = start_y + (card_width - 1 - rel_x)
                elif rotation == 180:
                    rel_x = orig_x - start_x
                    rel_y = orig_y - start_y
                    final_x = start_x + (card_width - 1 - rel_x)
                    final_y = start_y + (card_height - 1 - rel_y)
                else:  # rotation == 270
                    rel_x = orig_x - start_x
                    rel_y = orig_y - start_y
                    final_x = start_x + (card_height - 1 - rel_y)
                    final_y = start_y + rel_x
                
                # Draw pixel with bounds checking using rank color
                if 0 <= final_x < PANEL_WIDTH and 0 <= final_y < PANEL_HEIGHT:
                    buffer[final_y][final_x] = rank_color
    
    panel_buffers[panel_num].dirty = True

def draw_central_square_with_trump_and_scores_enhanced(panel_num, trump_suit):
    """Enhanced central square with trick counts for current hand"""
    buffer = panel_buffers[panel_num].back_buffer
    
    # Central square dimensions
    square_size = 24
    square_x = (PANEL_WIDTH - square_size) // 2
    square_y = (PANEL_HEIGHT - square_size) // 2
    
    # Draw LIGHT GREEN border around central square
    border_color = LIGHT_GREEN
    for i in range(square_size + 2):
        # Top and bottom borders
        if 0 <= square_x - 1 + i < PANEL_WIDTH:
            if 0 <= square_y - 1 < PANEL_HEIGHT:
                buffer[square_y - 1][square_x - 1 + i] = border_color
            if 0 <= square_y + square_size < PANEL_HEIGHT:
                buffer[square_y + square_size][square_x - 1 + i] = border_color
    
    for i in range(square_size + 2):
        # Left and right borders
        if 0 <= square_y - 1 + i < PANEL_HEIGHT:
            if 0 <= square_x - 1 < PANEL_WIDTH:
                buffer[square_y - 1 + i][square_x - 1] = border_color
            if 0 <= square_x + square_size < PANEL_WIDTH:
                buffer[square_y - 1 + i][square_x + square_size] = border_color
    
    # Draw trump symbol in center of square
    if trump_suit:
        symbol_data = symbols[trump_suit]
        color = SUIT_COLORS[trump_suit]
        trump_x = square_x + (square_size - 8) // 2
        trump_y = square_y + (square_size - 7) // 2
        
        for y, row in enumerate(symbol_data):
            for x, pixel in enumerate(row):
                if pixel == '1':
                    px = trump_x + x
                    py = trump_y + y
                    if square_x < px < square_x + square_size and square_y < py < square_y + square_size:
                        if 0 <= px < PANEL_WIDTH and 0 <= py < PANEL_HEIGHT:
                            buffer[py][px] = color
    
    # Score box dimensions
    score_box_size = 8
    
    # Team A trick count box (top-right corner) - GREEN
    team_a_x = square_x + square_size - score_box_size
    team_a_y = square_y
    
    # Team B trick count box (bottom-left corner) - BLUE
    team_b_x = square_x
    team_b_y = square_y + square_size - score_box_size
    
    # Draw Team A trick count box border (GREEN)
    for i in range(score_box_size):
        for j in range(score_box_size):
            px = team_a_x + i
            py = team_a_y + j
            if 0 <= px < PANEL_WIDTH and 0 <= py < PANEL_HEIGHT:
                if i == 0 or i == score_box_size-1 or j == 0 or j == score_box_size-1:
                    buffer[py][px] = GREEN
    
    # Draw Team B trick count box border (BLUE)
    for i in range(score_box_size):
        for j in range(score_box_size):
            px = team_b_x + i
            py = team_b_y + j
            if 0 <= px < PANEL_WIDTH and 0 <= py < PANEL_HEIGHT:
                if i == 0 or i == score_box_size-1 or j == 0 or j == score_box_size-1:
                    buffer[py][px] = BLUE
    
    # CRITICAL FIX: Display current hand trick counts (0-4 for half court, 0-8 for normal)
    team_a_tricks = game_state.get('tricks_won', {'A': 0, 'B': 0})['A']
    team_b_tricks = game_state.get('tricks_won', {'A': 0, 'B': 0})['B']
    
    # Display trick counts (should be 0-4 in half court mode)
    draw_small_number(panel_num, team_a_tricks, WHITE, team_a_x + 2, team_a_y + 2)
    draw_small_number(panel_num, team_b_tricks, WHITE, team_b_x + 2, team_b_y + 2)
    
    panel_buffers[panel_num].dirty = True


# UPDATED MAIN PANEL DISPLAY FUNCTION WITH HORIZONTAL CARDS
def display_main_panel_enhanced_horizontal_rotated(selected_cards, trump_suit, active_player=None):
    """Display main panel with horizontal rotated card display around central square"""
    clear_panel(4)  # Clear main panel
    
    # Draw central square with trump and scores
    draw_central_square_with_trump_and_scores_enhanced(4, trump_suit)
    
    # Draw each player's selected card horizontally with proper rotation
    for player, card in enumerate(selected_cards):
        if card is not None:
            draw_horizontal_card_with_rotation(4, card, player)
    
    # Draw blinking arrow indicator for active player
    if active_player is not None and game_state['phase'] == 'playing':
        current_time = time.time()
        
        # Update blink state every 0.5 seconds
        if current_time - game_state['last_arrow_update'] >= 0.5:
            game_state['arrow_blink_state'] = not game_state['arrow_blink_state']
            game_state['last_arrow_update'] = current_time
        
        # Only show arrow for active players
        active_players = game_state.get('active_players', [0, 1, 2, 3])
        if active_player in active_players:
            draw_player_arrow_indicator(4, active_player, game_state['arrow_blink_state'])
    
    panel_buffers[4].dirty = True
    update_display()

def display_main_panel(cards_in_trick, trump_suit, active_player=None):
    """Main panel display function - updated to use horizontal rotated layout with arrow"""
    selected_cards = []
    for i in range(4):
        if i < len(cards_in_trick) and cards_in_trick[i] is not None:
            selected_cards.append(cards_in_trick[i])
        else:
            selected_cards.append(None)
    
    display_main_panel_enhanced_horizontal_rotated(selected_cards, trump_suit, active_player)

def draw_multiline_text(panel_num, text, color, font_width=8, font_height=8, letter_spacing=2, line_spacing=2):
    """Enhanced multiline text with automatic wrapping and centering"""
    buffer = panel_buffers[panel_num].back_buffer
    max_chars_per_line = (PANEL_WIDTH + letter_spacing) // (font_width + letter_spacing)
    words = text.split()
    lines = []
    current_line = ""
    
    for word in words:
        if len(current_line + " " + word) <= max_chars_per_line or not current_line:
            if current_line:
                current_line += " " + word
            else:
                current_line = word
        else:
            lines.append(current_line)
            current_line = word
    
    if current_line:
        lines.append(current_line)
    
    # Calculate vertical centering
    total_height = len(lines) * font_height + (len(lines) - 1) * line_spacing
    start_y = max(0, (PANEL_HEIGHT - total_height) // 2)
    
    for idx, line in enumerate(lines):
        y = start_y + idx * (font_height + line_spacing)
        # Center each line horizontally
        line_width = len(line) * (font_width + letter_spacing) - letter_spacing
        x = max(0, (PANEL_WIDTH - line_width) // 2)
        draw_text_enhanced(panel_num, line, color, x, y, center=False, scale=1, letter_spacing=letter_spacing)

def display_half_court_option_animation():
    """Display half court option with pulsing animation"""
    for frame in range(150):  # 5 seconds at 30fps
        clear_panel(4)
        
        # Pulsing effect
        pulse = (math.sin(frame * 0.2) + 1) / 2
        brightness = int(180 + (75 * pulse))
        
        # Create pulsing colors
        pulse_white = (brightness, brightness, brightness)
        pulse_yellow = (brightness, brightness, 0)
        
        # Draw text
        draw_text_enhanced(4, "HALF COURT", pulse_white, PANEL_WIDTH // 2, 15, center=True, letter_spacing=1)
        draw_text_enhanced(4, "OPTION", pulse_yellow, PANEL_WIDTH // 2, 25, center=True, letter_spacing=1)
        draw_text_enhanced(4, "P OR O", pulse_white, PANEL_WIDTH // 2, 40, center=True, letter_spacing=1)
        draw_text_enhanced(4, "TO PLAY", pulse_yellow, PANEL_WIDTH // 2, 50, center=True, letter_spacing=1)
        
        panel_buffers[4].dirty = True
        update_display()
        time.sleep(0.033)

def get_non_trump_team_players():
    """Get players from the team that didn't select trump"""
    trump_team = game_state['trump_team']
    non_trump_team = 'B' if trump_team == 'A' else 'A'
    return TEAMS[non_trump_team]

def all_cards_10_or_below_fixed(cards):
    """FIXED: Check if all cards in hand are rank 10 or below using proper Omi ranking"""
    for card in cards:
        rank = card[1]  # Get rank from card tuple
        # In Omi: A=14, K=13, Q=12, J=11, 10=10, 9=9, 8=8, 7=7
        # For cancel trump: only 10, 9, 8, 7 are eligible (= 10)
        if rank not in ['10', '9', '8', '7']:
            return False
    return True

def display_cancel_trump_confirmation():
    """FIXED: Cancel trump confirmation - NO L/R text, NO cutoff"""
    clear_panel(4)
    
    # Title
    draw_text_enhanced_fixed(4, "CANCEL", WHITE, PANEL_WIDTH // 2, 8, center=True)
    draw_text_enhanced_fixed(4, "TRUMP?", YELLOW, PANEL_WIDTH // 2, 18, center=True)
    
    # YES/NO with proper spacing - NO moved further left to prevent cutoff
    yes_color = GREEN if game_state['cancel_trump_selection'] == 0 else WHITE
    no_color = RED if game_state['cancel_trump_selection'] == 1 else WHITE
    
    # YES at position 10, NO at position 40 (safer position)
    draw_text_enhanced_fixed(4, "YES", yes_color, 10, 35, center=False)   # Left side
    draw_text_enhanced_fixed(4, "NO", no_color, 40, 35, center=False)     # Right side (safer)
    
    # Arrow indicators
    if game_state['cancel_trump_selection'] == 0:
        draw_text_enhanced_fixed(4, ">", GREEN, 4, 35, center=False)      # Point to YES
    else:
        draw_text_enhanced_fixed(4, ">", RED, 34, 35, center=False)       # Point to NO
    
    panel_buffers[4].dirty = True

def display_canceled_cards_fixed(cards):
    """Display canceled trump cards with proper bitmap rendering"""
    for frame in range(90):  # 3 seconds
        clear_panel(4)
        
        # Pulsing title
        pulse = (math.sin(frame * 0.3) + 1) / 2
        title_brightness = int(150 + (105 * pulse))
        title_color = (title_brightness, title_brightness, 0)
        
        draw_text_enhanced_fixed(4, "TRUMP", title_color, PANEL_WIDTH // 2, 2, center=True)
        draw_text_enhanced_fixed(4, "CANCELED", title_color, PANEL_WIDTH // 2, 12, center=True)
        
        # Show the 4 cards in a 2x2 grid
        card_positions = [(8, 22), (40, 22), (8, 45), (40, 45)]
        
        for idx, card in enumerate(cards[:4]):
            if card is not None:
                x, y = card_positions[idx]
                suit, rank = card
                
                # Draw suit symbol
                if suit in symbols:
                    symbol_data = symbols[suit]
                    suit_color = SUIT_COLORS[suit]
                    
                    # Small suit symbol (8x8)
                    for sy, row in enumerate(symbol_data[:8]):
                        for sx, pixel in enumerate(row[:8]):
                            if pixel == '1':
                                px, py = x + sx, y + sy
                                if 0 <= px < PANEL_WIDTH and 0 <= py < PANEL_HEIGHT:
                                    panel_buffers[4].back_buffer[py][px] = suit_color
                
                # Draw rank below suit
                rank_y = y + 10
                draw_text_enhanced_fixed(4, str(rank), WHITE, x + 4, rank_y, center=True)
        
        panel_buffers[4].dirty = True
        commit_buffers()
        time.sleep(0.033)
    
    time.sleep(1)

def get_team_for_player(player):
    """Get team for player"""
    if player in TEAMS['A']:
        return 'A'
    else:
        return 'B'

def half_court_start_animation_fixed():
    """Fixed half court start animation with proper text sizing"""
    for frame in range(90):
        clear_panel(4)
        
        pulse = (math.sin(frame * 0.3) + 1) / 2
        brightness = int(150 + (105 * pulse))
        color = (brightness, brightness, 0)
        
        # Properly sized text for 64x64 panel
        draw_text_enhanced_fixed(4, "HALF", color, PANEL_WIDTH // 2, 15, center=True)
        draw_text_enhanced_fixed(4, "COURT", color, PANEL_WIDTH // 2, 25, center=True)
        draw_text_enhanced_fixed(4, "MODE", color, PANEL_WIDTH // 2, 40, center=True)
        
        panel_buffers[4].dirty = True
        update_display()
        time.sleep(0.033)
    
    time.sleep(1)

def new_round_animation_enhanced():
    """SPECTACULAR new round animation with perfect text and amazing effects"""
    particles = []
    
    # Phase 1: Build-up with particles (2 seconds)
    for frame in range(60):
        clear_panel(4)
        
        # Create particle bursts
        if frame % 10 == 0:
            particles.extend(create_particle_burst(
                PANEL_WIDTH // 2, PANEL_HEIGHT // 2, 
                count=15, colors=[YELLOW, ORANGE, WHITE]
            ))
        
        # Update and draw particles
        update_particles(particles)
        draw_particles(4, particles)
        
        # Growing energy rings
        center_x, center_y = PANEL_WIDTH // 2, PANEL_HEIGHT // 2
        for ring in range(5):
            radius = (frame + ring * 8) % 32
            if radius < 28:
                ring_brightness = int(255 * (1 - radius / 28))
                ring_color = (ring_brightness, ring_brightness // 2, 0)
                
                for angle in range(0, 360, 8):
                    x = center_x + int(radius * math.cos(math.radians(angle)))
                    y = center_y + int(radius * math.sin(math.radians(angle)))
                    if 0 <= x < PANEL_WIDTH and 0 <= y < PANEL_HEIGHT:
                        panel_buffers[4].back_buffer[y][x] = ring_color
        
        panel_buffers[4].dirty = True
        commit_buffers()
        time.sleep(0.033)
    
    # Phase 2: Perfect text reveal with effects (3 seconds)
    for frame in range(90):
        clear_panel(4)
        
        # Animated background
        for y in range(PANEL_HEIGHT):
            for x in range(PANEL_WIDTH):
                wave = math.sin((x + y + frame) * 0.1) * 0.5 + 0.5
                if wave > 0.7:
                    intensity = int(50 * (wave - 0.7) / 0.3)
                    panel_buffers[4].back_buffer[y][x] = (0, intensity, intensity)
        
        # Staggered perfect text appearance with spectacular effects
        if frame >= 15:
            effects = {'pulse': True, 'glow': True, 'shadow': True}
            draw_spectacular_text(4, "NEW", ORANGE, 8, effects)
        
        if frame >= 30:
            effects = {'pulse': True, 'glow': True, 'shadow': True}
            draw_spectacular_text(4, "ROUND", CYAN, 20, effects)
        
        if frame >= 45:
            effects = {'pulse': True, 'glow': True, 'shadow': True}
            draw_spectacular_text(4, "BEGINS", MAGENTA, 32, effects)
        
        # Show WiFi connection status
        display_connection_status()
        
        panel_buffers[4].dirty = True
        commit_buffers()
        time.sleep(0.033)
    
    time.sleep(1.0)

def half_court_winner_animation(winner_info, winning_team, is_half_court_win):
    """FIXED: Half Court winner animation with CLEAR defeated team display"""
    if is_half_court_win:
        # Half court player wins all 4 tricks
        text = f"HALF COURT PLAYER {winner_info + 1} WINS!"
        color = YELLOW
        defeated_team = game_state['trump_team']  # Trump team is defeated
        print(f"Half court player {winner_info + 1} wins all 4 tricks!")
        print(f"DEFEATED TEAM: {defeated_team} must scan cards")
    else:
        # Trump team defeats half court player
        half_court_team = game_state['half_court_team']
        defeated_team = half_court_team  # Half court team is defeated
        text = f"TEAM {winning_team} DEFEATS TEAM {defeated_team}!"
        color = GREEN if winning_team == 'A' else BLUE
        print(f"Trump Team {winning_team} defeats half court!")
        print(f"DEFEATED TEAM: {defeated_team} must scan cards")
    
    # Clear all panels first
    clear_all_panels()
    
    # Enhanced letter patterns with better spacing
def get_letter_pattern(letter):
    """Enhanced letter patterns - KEEPING ORIGINAL FUNCTION NAME"""
    return get_perfect_letter_pattern(letter)

    # Step 1: Show winning team
    clear_panel(4)
    if is_half_court_win:
        draw_text_enhanced_fixed(4, "HALF COURT", color, PANEL_WIDTH // 2, 5, center=True)
        draw_text_enhanced_fixed(4, "PLAYER", color, PANEL_WIDTH // 2, 15, center=True)
        draw_text_enhanced_fixed(4, f"{winner_info + 1}", color, PANEL_WIDTH // 2, 25, center=True)
        draw_text_enhanced_fixed(4, "WINS!", color, PANEL_WIDTH // 2, 35, center=True)
        draw_text_enhanced_fixed(4, f"TEAM {defeated_team}", RED, PANEL_WIDTH // 2, 50, center=True)
        draw_text_enhanced_fixed(4, "DEFEATED", RED, PANEL_WIDTH // 2, 60, center=True)
    else:
        draw_text_enhanced_fixed(4, f"TEAM {winning_team}", color, PANEL_WIDTH // 2, 10, center=True)
        draw_text_enhanced_fixed(4, "DEFEATS", color, PANEL_WIDTH // 2, 25, center=True)
        draw_text_enhanced_fixed(4, f"TEAM {defeated_team}!", RED, PANEL_WIDTH // 2, 40, center=True)
    panel_buffers[4].dirty = True
    commit_buffers()
    time.sleep(2.0)
    
    # Step 2: Show defeated team must scan
    clear_panel(4)
    draw_text_enhanced_fixed(4, f"DEFEATED", RED, PANEL_WIDTH // 2, 10, center=True)
    draw_text_enhanced_fixed(4, f"TEAM {defeated_team}", RED, PANEL_WIDTH // 2, 20, center=True)
    draw_text_enhanced_fixed(4, "MUST SCAN", YELLOW, PANEL_WIDTH // 2, 35, center=True)
    draw_text_enhanced_fixed(4, "2 CARDS", YELLOW, PANEL_WIDTH // 2, 45, center=True)
    panel_buffers[4].dirty = True
    commit_buffers()
    time.sleep(2.0)
    
    # Continue with spectacular animation...
    for frame in range(120):
        clear_panel(4)
        
        # Multiple expanding circles
        center_x, center_y = PANEL_WIDTH // 2, PANEL_HEIGHT // 2
        for explosion in range(4):
            radius = (frame + explosion * 15) % 35
            if radius < 30:
                for angle in range(0, 360, 12):
                    x = center_x + int(radius * math.cos(math.radians(angle)))
                    y = center_y + int(radius * math.sin(math.radians(angle)))
                    if 0 <= x < PANEL_WIDTH and 0 <= y < PANEL_HEIGHT:
                        alpha = 1 - (radius / 30)
                        display_color = (
                            int(color[0] * alpha), 
                            int(color[1] * alpha), 
                            int(color[2] * alpha)
                        )
                        panel_buffers[4].back_buffer[y][x] = display_color
        
        # Sparkles
        for _ in range(10):
            x = random.randint(0, PANEL_WIDTH - 1)
            y = random.randint(0, PANEL_HEIGHT - 1)
            if random.random() > 0.6:
                panel_buffers[4].back_buffer[y][x] = WHITE
        
        # Show defeated team clearly
        draw_text_enhanced_fixed(4, f"TEAM {defeated_team}", RED, PANEL_WIDTH // 2, 15, center=True)
        draw_text_enhanced_fixed(4, "SCANS", YELLOW, PANEL_WIDTH // 2, 30, center=True)
        draw_text_enhanced_fixed(4, "CARDS", YELLOW, PANEL_WIDTH // 2, 45, center=True)
        
        panel_buffers[4].dirty = True
        update_display()
        time.sleep(0.033)
    
    time.sleep(2)

def wrap_text_enhanced(text, max_chars_per_line=7, max_lines=6):
    """Enhanced text wrapping for better display"""
    words = text.split()
    lines = []
    current_line = ""
    
    for word in words:
        test_line = current_line + (" " if current_line else "") + word
        if len(test_line) <= max_chars_per_line:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
                current_line = word
            else:
                # Word is too long, split it
                lines.append(word[:max_chars_per_line])
                current_line = word[max_chars_per_line:] if len(word) > max_chars_per_line else ""
        
        if len(lines) >= max_lines:
            break
    
    if current_line and len(lines) < max_lines:
        lines.append(current_line)
    
    return lines

def draw_multiline_text_enhanced(panel_num, text, color, center_y=32, max_lines=6, scale=1, line_spacing=3):
    """Enhanced multiline text with proper spacing"""
    lines = wrap_text_enhanced(text, max_chars_per_line=7, max_lines=max_lines)
    line_height = (8 * scale) + line_spacing
    total_height = len(lines) * line_height - line_spacing
    start_y = max(2, center_y - (total_height // 2))
    
    for i, line in enumerate(lines):
        y_pos = start_y + (i * line_height)
        if y_pos + (8 * scale) <= PANEL_HEIGHT:
            draw_text_enhanced(panel_num, line, color, PANEL_WIDTH // 2, y_pos, center=True, scale=scale, letter_spacing=1)

def update_display():
    """Update display at controlled rate (60fps max)"""
    current_time = time.time()
    if current_time - game_state['last_update'] > 0.016:  # ~60fps
        commit_buffers()
        game_state['last_update'] = current_time

def display_player_hand(panel_num, hand, selected_index=-1):
    """Enhanced hand display with smooth animations"""
    clear_panel(panel_num)
    for i, card in enumerate(hand):
        if card is not None:
            pos = CARD_POSITIONS[i]
            draw_card(panel_num, pos[0], pos[1], card, selected=(i == selected_index))
    update_display()

def draw_large_suit_corner(panel_num, suit):
    """Draw trump suit in top left corner with proper size"""
    buffer = panel_buffers[panel_num].back_buffer
    symbol_data = symbols[suit]
    color = SUIT_COLORS[suit]
    
    # Draw at smaller scale in corner
    scale = 1
    start_x = 2
    start_y = 2
    
    for y, row in enumerate(symbol_data[:12]):
        for x, pixel in enumerate(row[:12]):
            if pixel == '1':
                px = start_x + x * scale
                py = start_y + y * scale
                if 0 <= px < PANEL_WIDTH and 0 <= py < PANEL_HEIGHT:
                    buffer[py][px] = color
    
    panel_buffers[panel_num].dirty = True

def draw_progress_bar_enhanced(panel_num, progress):
    """Enhanced progress bar - KEEPING ORIGINAL NAME"""
    buffer = panel_buffers[panel_num].back_buffer
    bar_width = 50
    bar_height = 6
    bar_x = (PANEL_WIDTH - bar_width) // 2
    bar_y = 45
    
    # Draw border
    border_color = WHITE
    for x in range(bar_width + 2):
        if 0 <= bar_x - 1 + x < PANEL_WIDTH:
            if 0 <= bar_y - 1 < PANEL_HEIGHT:
                buffer[bar_y - 1][bar_x - 1 + x] = border_color
            if 0 <= bar_y + bar_height < PANEL_HEIGHT:
                buffer[bar_y + bar_height][bar_x - 1 + x] = border_color
    
    for y in range(bar_height + 2):
        if 0 <= bar_y - 1 + y < PANEL_HEIGHT:
            if 0 <= bar_x - 1 < PANEL_WIDTH:
                buffer[bar_y - 1 + y][bar_x - 1] = border_color
            if 0 <= bar_x + bar_width < PANEL_WIDTH:
                buffer[bar_y - 1 + y][bar_x + bar_width] = border_color
    
    # Fill progress with gradient
    fill_width = int((progress / 100.0) * bar_width)
    for x in range(fill_width):
        for y in range(bar_height):
            px = bar_x + x
            py = bar_y + y
            if 0 <= px < PANEL_WIDTH and 0 <= py < PANEL_HEIGHT:
                # Create gradient from green to yellow
                gradient_factor = x / max(1, fill_width - 1)
                red = int(gradient_factor * 255)
                green = 255
                blue = 0
                buffer[py][px] = (red, green, blue)
    
    panel_buffers[panel_num].dirty = True

def draw_pulsing_text_enhanced(panel_num, text, base_color, frame):
    """Enhanced pulsing text with smooth animation"""
    pulse = (math.sin(frame * 0.15) + 1) / 2  # Slower, smoother pulse
    brightness = int(150 + (105 * pulse))  # 150 to 255
    
    color = (
        min(255, int(base_color[0] * brightness / 255)),
        min(255, int(base_color[1] * brightness / 255)),
        min(255, int(base_color[2] * brightness / 255))
    )
    
    draw_multiline_text_enhanced(panel_num, text, color)

def draw_large_suit_centered(panel_num, suit, size=2):
    """Draw large suit symbol in center of panel with proper scaling"""
    buffer = panel_buffers[panel_num].back_buffer
    symbol_data = symbols[suit]
    color = SUIT_COLORS[suit]
    
    # Calculate center position for the symbol
    symbol_width = 16 * size
    symbol_height = 16 * size
    start_x = (PANEL_WIDTH - symbol_width) // 2
    start_y = (PANEL_HEIGHT - symbol_height) // 2 + 5  # Slightly lower for text above
    
    for y, row in enumerate(symbol_data[:16]):
        for x, pixel in enumerate(row[:16]):
            if pixel == '1':
                for dy in range(size):
                    for dx in range(size):
                        px = start_x + x * size + dx
                        py = start_y + y * size + dy
                        if 0 <= px < PANEL_WIDTH and 0 <= py < PANEL_HEIGHT:
                            buffer[py][px] = color
    
    panel_buffers[panel_num].dirty = True

def draw_enhanced_sad_face(panel_num):
    """Draw enhanced sad face with better graphics"""
    buffer = panel_buffers[panel_num].back_buffer
    center_x = PANEL_WIDTH // 2
    center_y = PANEL_HEIGHT // 2
    
    # Face circle with gradient
    for radius in range(12, 18):
        for angle in range(0, 360, 3):
            x = center_x + int(radius * math.cos(math.radians(angle)))
            y = center_y + int(radius * math.sin(math.radians(angle)))
            if 0 <= x < PANEL_WIDTH and 0 <= y < PANEL_HEIGHT:
                brightness = int(255 * (18 - radius) / 6)
                buffer[y][x] = (brightness, brightness, 0)
    
    # Eyes with better shape
    for x in range(center_x - 7, center_x - 3):
        for y in range(center_y - 6, center_y - 2):
            if 0 <= x < PANEL_WIDTH and 0 <= y < PANEL_HEIGHT:
                buffer[y][x] = BLACK
    
    for x in range(center_x + 3, center_x + 7):
        for y in range(center_y - 6, center_y - 2):
            if 0 <= x < PANEL_WIDTH and 0 <= y < PANEL_HEIGHT:
                buffer[y][x] = BLACK
    
    # Enhanced sad mouth
    for x in range(center_x - 10, center_x + 10):
        y_offset = abs(x - center_x) // 3
        y = center_y + 10 - y_offset
        if 0 <= x < PANEL_WIDTH and 0 <= y < PANEL_HEIGHT:
            buffer[y][x] = BLACK
        # Add thickness to mouth
        if 0 <= x < PANEL_WIDTH and 0 <= y + 1 < PANEL_HEIGHT:
            buffer[y + 1][x] = BLACK
    
    panel_buffers[panel_num].dirty = True

def draw_trump_selection_suits_enhanced(panel_num):
    """Draw four suits for trump selection with better layout under text"""
    buffer = panel_buffers[panel_num].back_buffer
    suits = ['hearts', 'diamonds', 'clubs', 'spades']
    # Position suits under the text - arranged in 2x2 grid
    positions = [(16, 25), (40, 25), (16, 45), (40, 45)]
    
    for i, suit in enumerate(suits):
        color = SUIT_COLORS[suit]
        symbol_data = symbols[suit]
        start_x, start_y = positions[i]
        
        # Draw suit with better scaling
        for y, row in enumerate(symbol_data[:16]):
            for x, pixel in enumerate(row[:16]):
                if pixel == '1':
                    px = start_x + x
                    py = start_y + y
                    if 0 <= px < PANEL_WIDTH and 0 <= py < PANEL_HEIGHT:
                        buffer[py][px] = color
    
    panel_buffers[panel_num].dirty = True

def animate_trump_to_corner_enhanced_realistic(trump_suit):
    """Enhanced realistic trump animation with smooth movement to corner"""
    symbol_data = symbols[trump_suit]
    color = SUIT_COLORS[trump_suit]
    
    # Start position (center, larger)
    start_x = (PANEL_WIDTH - 32) // 2
    start_y = 35  # Start from where the announcement symbol was
    start_scale = 2
    
    # End position (top left corner, smaller)
    end_x = 2
    end_y = 2
    end_scale = 1
    
    # Animation parameters
    frames = 45  # Longer animation for smoother movement
    
    for frame in range(frames):
        clear_panel(4)
        
        # Calculate smooth easing (ease-out cubic for natural movement)
        progress = frame / (frames - 1)
        eased_progress = 1 - (1 - progress) ** 3
        
        # Interpolate position
        current_x = int(start_x + (end_x - start_x) * eased_progress)
        current_y = int(start_y + (end_y - start_y) * eased_progress)
        
        # Interpolate scale (smooth shrinking)
        current_scale = start_scale + (end_scale - start_scale) * eased_progress
        
        # Add rotation effect for more realism
        rotation_angle = progress * 360  # Full rotation during movement
        
        # Draw the suit symbol with current transformations
        for y, row in enumerate(symbol_data[:16]):
            for x, pixel in enumerate(row[:16]):
                if pixel == '1':
                    # Apply scaling
                    for sy in range(int(current_scale)):
                        for sx in range(int(current_scale)):
                            # Calculate pixel position
                            px = current_x + int(x * current_scale) + sx
                            py = current_y + int(y * current_scale) + sy
                            
                            # Add slight wobble effect for realism
                            wobble_x = int(2 * math.sin(frame * 0.3 + x * 0.1))
                            wobble_y = int(1 * math.cos(frame * 0.4 + y * 0.1))
                            
                            final_x = px + wobble_x
                            final_y = py + wobble_y
                            
                            # Draw with bounds checking
                            if 0 <= final_x < PANEL_WIDTH and 0 <= final_y < PANEL_HEIGHT:
                                # Add fading effect as it moves
                                fade_factor = 1 - (progress * 0.3)  # Slight fade
                                faded_color = (
                                    int(color[0] * fade_factor),
                                    int(color[1] * fade_factor),
                                    int(color[2] * fade_factor)
                                )
                                panel_buffers[4].back_buffer[final_y][final_x] = faded_color
        
        # Add trail effect
        if frame > 5:
            trail_alpha = 0.3
            trail_x = int(start_x + (end_x - start_x) * (progress - 0.1))
            trail_y = int(start_y + (end_y - start_y) * (progress - 0.1))
            trail_scale = start_scale + (end_scale - start_scale) * (progress - 0.1)
            
            for y, row in enumerate(symbol_data[:16]):
                for x, pixel in enumerate(row[:16]):
                    if pixel == '1':
                        px = trail_x + int(x * trail_scale)
                        py = trail_y + int(y * trail_scale)
                        if 0 <= px < PANEL_WIDTH and 0 <= py < PANEL_HEIGHT:
                            trail_color = (
                                int(color[0] * trail_alpha),
                                int(color[1] * trail_alpha),
                                int(color[2] * trail_alpha)
                            )
                            panel_buffers[4].back_buffer[py][px] = trail_color
        
        panel_buffers[4].dirty = True
        update_display()
        time.sleep(0.033)
    
    # Final position - ensure it's exactly in the corner
    clear_panel(4)
    draw_large_suit_corner(4, trump_suit)
    panel_buffers[4].dirty = True
    update_display()
    time.sleep(0.5)

def check_half_court_winner():
    """Check winner in half court mode"""
    if not game_state.get('half_court_mode', False):
        return None
    
    half_court_player = game_state['half_court_player']
    half_court_team = game_state['half_court_team']
    trump_team = game_state['trump_team']
    
    # Half court player needs all 4 tricks to win
    if game_state['tricks_won'][half_court_team] == 4:
        return half_court_player, True  # Half court player wins
    elif game_state['tricks_won'][trump_team] >= 1:
        return trump_team, False  # Trump team wins (half court player lost)
    
    return None

def initialize_wifi_token_system():
    """Initialize ESP32 WiFi token system"""
    print("Initializing ESP32 WiFi Token System...")
    
    try:
        # Try automatic discovery first
        game_state['wifi_manager'] = ESP32WiFiManager()
        
        if game_state['wifi_manager'].connected:
            # Reset tokens to 10 at start
            game_state['wifi_manager'].reset_tokens()
            game_state['connection_status'] = 'connected'
            print("WiFi Token system connected successfully!")
            return True
        else:
            game_state['connection_status'] = 'failed'
            print("Failed to connect to ESP32")
            return False
            
    except Exception as e:
        print(f"WiFi token system initialization failed: {e}")
        game_state['connection_status'] = 'error'
        return False

def handle_esp32_wifi_messages():
    """Handle incoming WiFi messages from ESP32 with improved parsing"""
    if not game_state['wifi_manager']:
        return
    
    message = game_state['wifi_manager'].get_message()
    if message:
        try:
            if message.startswith("SCAN_READY:"):
                # Format: SCAN_READY:A:3
                parts = message.split(':')
                if len(parts) >= 3:
                    team = parts[1]
                    scans = int(parts[2])
                    game_state['show_scan_ready'] = True
                    game_state['scan_ready_timer'] = time.time()
                    game_state['scan_team'] = team
                    game_state['scans_required'] = scans
                    print(f"ESP32 ready for {scans} scans by DEFEATED team {team}")
            
            elif message.startswith("SCAN_PROGRESS:"):
                # Format: SCAN_PROGRESS:A:2:3:8:7 (team:completed:required:tokensA:tokensB)
                parts = message.split(':')
                if len(parts) >= 6:
                    try:
                        team = parts[1]
                        completed = int(parts[2])
                        required = int(parts[3])
                        tokens_a = int(parts[4])
                        tokens_b = int(parts[5])
                        
                        game_state['scans_completed'] = completed
                        game_state['show_scans_left'] = True
                        game_state['scans_left_timer'] = time.time()
                        game_state['team_tokens'] = {'A': tokens_a, 'B': tokens_b}
                        
                        print(f"Scan progress: DEFEATED team {team} - {completed}/{required}, Tokens A:{tokens_a} B:{tokens_b}")
                    except ValueError as e:
                        print(f"Error parsing SCAN_PROGRESS values: {e}")
                        print(f"Raw message: {message}")
                        print(f"Parts: {parts}")
                else:
                    print(f"Invalid SCAN_PROGRESS format: {message}")
            
            elif message.startswith("SCAN_COMPLETE:"):
                # Format: SCAN_COMPLETE:A
                parts = message.split(':')
                if len(parts) >= 2:
                    team = parts[1]
                    game_state['scanning_active'] = False
                    game_state['show_scans_left'] = False  # Stop showing scans left
                    print(f"DEFEATED team {team} completed token scanning")
                    
                    # Set flag to handle trump selection transition
                    game_state['scanning_just_completed'] = True
            
            elif message.startswith("TOKENS:"):
                # Format: TOKENS:A:8:B:7
                parts = message.split(':')
                if len(parts) >= 5:
                    try:
                        game_state['team_tokens']['A'] = int(parts[2])
                        game_state['team_tokens']['B'] = int(parts[4])
                        print(f"Token update - A: {parts[2]}, B: {parts[4]}")
                    except ValueError as e:
                        print(f"Error parsing TOKENS values: {e}")
                        print(f"Raw message: {message}")
            
            elif message.startswith("GAME_OVER:"):
                # Format: GAME_OVER:A_WINS or GAME_OVER:B_WINS
                parts = message.split(':')
                if len(parts) >= 2:
                    winner = parts[1].split('_')[0]  # Extract A or B
                    show_token_game_over_wifi(winner)
            
            elif message == "PONG":
                # Heartbeat response
                game_state['connection_status'] = 'connected'
            
            else:
                print(f"Unhandled ESP32 message: {message}")
                
        except Exception as e:
            print(f"Error handling ESP32 message: {e}")
            print(f"Message: {message}")
            import traceback
            traceback.print_exc()

def trigger_wifi_token_scan(winning_team, num_scans):
    """FIXED: Trigger token scanning via WiFi after team wins round with immediate display"""
    if game_state['wifi_manager'] and game_state['wifi_manager'].connected:
        game_state['scanning_active'] = True
        game_state['scan_team'] = winning_team
        game_state['scans_required'] = num_scans
        game_state['scans_completed'] = 0
        
        # FIXED: Immediately show scan ready display
        game_state['show_scan_ready'] = True
        game_state['scan_ready_timer'] = time.time()
        print(f"IMMEDIATE DISPLAY: Team {winning_team} ready for {num_scans} scans")
        
        # Send command to ESP32
        success = game_state['wifi_manager'].start_token_scan(winning_team, num_scans)
        if success:
            print(f"Started WiFi token scan: DEFEATED Team {winning_team} needs {num_scans} scans")
            return True
        else:
            # If ESP32 command fails, still show the display
            print(f"ESP32 command failed but showing scan display anyway")
            return False
    else:
        print("ESP32 not connected via WiFi!")
        # Even without WiFi, show the scan ready display
        game_state['show_scan_ready'] = True
        game_state['scan_ready_timer'] = time.time()
        game_state['scan_team'] = winning_team
        game_state['scans_required'] = num_scans
        print(f"NO WiFi: Still showing Team {winning_team} ready for {num_scans} scans display")
        return False

def display_scans_left_animation():
    """Display 'X SCANS LEFT' animation with proper timing"""
    if not game_state['show_scans_left']:
        return
    
    elapsed = time.time() - game_state['scans_left_timer']
    if elapsed >= 3.0:  # Show for 3 seconds
        game_state['show_scans_left'] = False
        print(f"Scans left display finished")
        return
    
    clear_panel(4)
    
    # Pulsing animation
    pulse = (math.sin(elapsed * 3) + 1) / 2
    brightness = int(150 + (105 * pulse))
    color = (brightness, brightness, 0)
    
    scans_left = game_state['scans_required'] - game_state['scans_completed']
    team = game_state['scan_team']
    
    # Display scans remaining
    draw_text_enhanced_fixed(4, f"TEAM {team}", color, PANEL_WIDTH // 2, 8, center=True)
    draw_text_enhanced_fixed(4, f"{scans_left}", color, PANEL_WIDTH // 2, 20, center=True)
    draw_text_enhanced_fixed(4, "SCANS", color, PANEL_WIDTH // 2, 32, center=True)
    draw_text_enhanced_fixed(4, "LEFT", color, PANEL_WIDTH // 2, 44, center=True)
    
    panel_buffers[4].dirty = True
    update_display()

def display_scan_ready_animation():
    """FIXED: Display 'DEFEATED TEAM X READY FOR Y SCANS' animation with better timing"""
    if not game_state['show_scan_ready']:
        return
    
    elapsed = time.time() - game_state['scan_ready_timer']
    if elapsed >= 3.0:  # REDUCED from 5.0 to 3.0 seconds for faster display
        game_state['show_scan_ready'] = False
        print(f"Scan ready display finished for team {game_state['scan_team']}")
        return
    
    clear_panel(4)
    
    # Pulsing animation
    pulse = (math.sin(elapsed * 3) + 1) / 2
    brightness = int(150 + (105 * pulse))
    color = (brightness, brightness, 0)
    
    team = game_state['scan_team']
    scans = game_state['scans_required']
    
    # FIXED: Clear messaging about DEFEATED team
    draw_text_enhanced_fixed(4, f"DEFEATED", color, PANEL_WIDTH // 2, 5, center=True)
    draw_text_enhanced_fixed(4, f"TEAM {team}", color, PANEL_WIDTH // 2, 15, center=True)
    draw_text_enhanced_fixed(4, "READY", color, PANEL_WIDTH // 2, 25, center=True)
    draw_text_enhanced_fixed(4, "FOR", color, PANEL_WIDTH // 2, 35, center=True)
    draw_text_enhanced_fixed(4, f"{scans} SCANS", color, PANEL_WIDTH // 2, 45, center=True)
    
    panel_buffers[4].dirty = True
    update_display()

def display_scan_ready_animation():
    """FIXED: Display 'DEFEATED TEAM X READY FOR Y SCANS' animation with correct messaging"""
    if not game_state['show_scan_ready']:
        return
    
    elapsed = time.time() - game_state['scan_ready_timer']
    if elapsed >= 3.0:  # Show for 3 seconds
        game_state['show_scan_ready'] = False
        print(f"Scan ready display finished for DEFEATED team {game_state['scan_team']}")
        return
    
    clear_panel(4)
    
    # Pulsing animation
    pulse = (math.sin(elapsed * 3) + 1) / 2
    brightness = int(150 + (105 * pulse))
    color = (brightness, brightness, 0)
    
    team = game_state['scan_team']
    scans = game_state['scans_required']
    
    # Clear messaging about DEFEATED team
    draw_text_enhanced_fixed(4, f"DEFEATED", color, PANEL_WIDTH // 2, 5, center=True)
    draw_text_enhanced_fixed(4, f"TEAM {team}", color, PANEL_WIDTH // 2, 15, center=True)
    draw_text_enhanced_fixed(4, "READY", color, PANEL_WIDTH // 2, 25, center=True)
    draw_text_enhanced_fixed(4, "FOR", color, PANEL_WIDTH // 2, 35, center=True)
    draw_text_enhanced_fixed(4, f"{scans} SCANS", color, PANEL_WIDTH // 2, 45, center=True)
    
    panel_buffers[4].dirty = True
    update_display()

def display_connection_status():
    """Display WiFi connection status on main panel - KEEPING ORIGINAL NAME"""
    if game_state['connection_status'] == 'connected':
        # Small green dot in corner
        panel_buffers[4].back_buffer[1][PANEL_WIDTH-2] = (0, 255, 0)
        panel_buffers[4].back_buffer[1][PANEL_WIDTH-3] = (0, 255, 0)
        panel_buffers[4].back_buffer[2][PANEL_WIDTH-2] = (0, 255, 0)
        panel_buffers[4].back_buffer[2][PANEL_WIDTH-3] = (0, 255, 0)
    elif game_state['connection_status'] == 'failed':
        # Small red dot in corner
        panel_buffers[4].back_buffer[1][PANEL_WIDTH-2] = (255, 0, 0)
        panel_buffers[4].back_buffer[1][PANEL_WIDTH-3] = (255, 0, 0)
        panel_buffers[4].back_buffer[2][PANEL_WIDTH-2] = (255, 0, 0)
        panel_buffers[4].back_buffer[2][PANEL_WIDTH-3] = (255, 0, 0)

def show_token_game_over_wifi(winner_team):
    """Show token game over animation"""
    for frame in range(120):
        clear_panel(4)
        
        # Spectacular winner animation
        pulse = (math.sin(frame * 0.2) + 1) / 2
        brightness = int(150 + (105 * pulse))
        
        if winner_team == 'A':
            color = (0, brightness, 0)  # Green
        else:
            color = (0, 0, brightness)  # Blue
        
        draw_text_enhanced_fixed(4, "TOKEN", color, PANEL_WIDTH // 2, 5, center=True)
        draw_text_enhanced_fixed(4, "GAME", color, PANEL_WIDTH // 2, 15, center=True)
        draw_text_enhanced_fixed(4, "OVER", color, PANEL_WIDTH // 2, 25, center=True)
        draw_text_enhanced_fixed(4, f"TEAM {winner_team}", color, PANEL_WIDTH // 2, 40, center=True)
        draw_text_enhanced_fixed(4, "WINS!", color, PANEL_WIDTH // 2, 50, center=True)
        
        panel_buffers[4].dirty = True
        update_display()
        time.sleep(0.033)
    
    time.sleep(3)

def team_won_round_animation_enhanced_wifi(winning_team):
    """Enhanced team won animation with CLEAR defeated team display"""
    defeated_team = 'B' if winning_team == 'A' else 'A'
    text = f"TEAM {winning_team} WON THE ROUND"
    team_color = GREEN if winning_team == 'A' else BLUE
    
    print(f"WINNING TEAM: {winning_team}")
    print(f"DEFEATED TEAM: {defeated_team} must scan cards")
    
    # Step 1: Show winning team
    for frame in range(60):
        clear_panel(4)
        
        # Draw expanding celebration rings
        center_x, center_y = PANEL_WIDTH // 2, PANEL_HEIGHT // 2
        for ring in range(3):
            radius = (frame + ring * 10) % 30
            if radius < 25:
                for angle in range(0, 360, 15):
                    x = center_x + int(radius * math.cos(math.radians(angle)))
                    y = center_y + int(radius * math.sin(math.radians(angle)))
                    if 0 <= x < PANEL_WIDTH and 0 <= y < PANEL_HEIGHT:
                        alpha = 1 - (radius / 25)
                        color = (int(team_color[0] * alpha), int(team_color[1] * alpha), int(team_color[2] * alpha))
                        panel_buffers[4].back_buffer[y][x] = color
        
        draw_text_enhanced_fixed(4, f"TEAM {winning_team}", team_color, PANEL_WIDTH // 2, 15, center=True)
        draw_text_enhanced_fixed(4, "WINS", team_color, PANEL_WIDTH // 2, 30, center=True)
        draw_text_enhanced_fixed(4, f"TEAM {defeated_team}", RED, PANEL_WIDTH // 2, 50, center=True)
        
        display_connection_status()
        update_display()
        time.sleep(0.05)
    
    # Step 2: Show defeated team must scan
    clear_panel(4)
    draw_text_enhanced_fixed(4, f"DEFEATED", RED, PANEL_WIDTH // 2, 10, center=True)
    draw_text_enhanced_fixed(4, f"TEAM {defeated_team}", RED, PANEL_WIDTH // 2, 20, center=True)
    draw_text_enhanced_fixed(4, "MUST SCAN", YELLOW, PANEL_WIDTH // 2, 35, center=True)
    
    # Show number of cards to scan based on game mode
    if game_state.get('half_court_mode', False):
        cards_to_scan = 2
    elif game_state.get('full_court_mode', False):
        cards_to_scan = 3
    else:
        # Normal game - check for kapothi or normal win
        if game_state['tricks_won'][winning_team] == 8:
            cards_to_scan = 3  # Kapothi
        elif winning_team == game_state['trump_team']:
            cards_to_scan = 1  # Trump team wins normally
        else:
            cards_to_scan = 2  # Non-trump team wins
    
    draw_text_enhanced_fixed(4, f"{cards_to_scan} CARDS", YELLOW, PANEL_WIDTH // 2, 45, center=True)
    panel_buffers[4].dirty = True
    commit_buffers()
    time.sleep(2.0)
    
    # Trigger WiFi token scanning for DEFEATED team
    if cards_to_scan > 0:
        trigger_wifi_token_scan(defeated_team, cards_to_scan)
    
    time.sleep(1)

def handle_full_court_completion():
    """FIXED: Handle completion of full court round with proper team detection and scanning logic"""
    if not game_state.get('full_court_mode', False):
        return False
    
    full_court_team = game_state['full_court_team']
    trump_team = game_state['trump_team']
    
    # Check if full court player won all 8 tricks
    if game_state['tricks_won'][full_court_team] == 8:
        # Full court player wins
        full_court_player = game_state['full_court_player']
        print(f"Full court player {full_court_player + 1} (Team {full_court_team}) wins all 8 tricks!")
        
        # Show animation with full court player as winner
        full_court_winner_animation(full_court_player, full_court_team, True)
        
        # DEFEATED team (trump team/opposing team) must scan cards
        defeated_team = 'B' if full_court_team == 'A' else 'A'
        print(f"DEFEATED TEAM: {defeated_team} (opposing team) must scan 3 cards")
        trigger_wifi_token_scan(defeated_team, 3)
        
        return True
        
    # Check if full court player lost any trick
    elif game_state['tricks_won'][trump_team] >= 1:
        # Full court player lost - trump team (NON-TRUMP team) wins
        print(f"NON-TRUMP Team {trump_team} defeats full court player!")
        
        # Show animation with trump team as winner (defeating full court)
        full_court_winner_animation(None, trump_team, False)
        
        # DEFEATED team (full court team) must scan cards
        defeated_team = full_court_team
        print(f"DEFEATED TEAM: {defeated_team} (full court team) must scan 3 cards")
        trigger_wifi_token_scan(defeated_team, 3)
        
        return True
    
    return False

def handle_half_court_completion():
    """FIXED: Handle completion of half court round with proper team detection and scanning logic"""
    half_court_result = check_half_court_winner()
    if half_court_result:
        winner_info, is_half_court_win = half_court_result
        
        if is_half_court_win:
            # Half court player wins all 4 tricks
            half_court_player = game_state['half_court_player']
            half_court_team = game_state['half_court_team']
            trump_team = game_state['trump_team']
            
            print(f"Half court player {half_court_player + 1} (Team {half_court_team}) wins all 4 tricks!")
            
            # Show animation with half court player as winner
            half_court_winner_animation(half_court_player, half_court_team, True)
            
            # DEFEATED team (trump team) must scan cards
            defeated_team = trump_team
            print(f"DEFEATED TEAM: {defeated_team} (trump team) must scan 2 cards")
            trigger_wifi_token_scan(defeated_team, 2)
            
        else:
            # Trump team (NON-TRUMP team) defeats half court player
            trump_team = game_state['trump_team']
            half_court_team = game_state['half_court_team']
            
            print(f"NON-TRUMP Team {trump_team} defeats half court player!")
            
            # Show animation with trump team as winner (defeating half court)
            half_court_winner_animation(None, trump_team, False)
            
            # DEFEATED team (half court team) must scan cards
            defeated_team = half_court_team
            print(f"DEFEATED TEAM: {defeated_team} (half court team) must scan 2 cards")
            trigger_wifi_token_scan(defeated_team, 2)
        
        return True
    return False

def handle_scanning_completion_and_trump_selection():
    """FIXED: Handle the transition from scanning completion to trump selection with NEW ROUND animation"""
    global game_state, hands, remaining_cards, selected_indices
    
    # Wait for scanning to complete
    if game_state.get('scanning_active', False):
        print("Still scanning, waiting...")
        return False  # Still scanning, don't proceed
    
    # FIXED: Ensure scan displays are cleared immediately
    if game_state.get('show_scan_ready', False) or game_state.get('show_scans_left', False):
        print("Clearing scan displays...")
        game_state['show_scan_ready'] = False
        game_state['show_scans_left'] = False
    
    # Show "SCANNING COMPLETE" message
    clear_panel(4)
    draw_text_enhanced_fixed(4, "SCANNING", GREEN, PANEL_WIDTH // 2, 15, center=True)
    draw_text_enhanced_fixed(4, "COMPLETE", GREEN, PANEL_WIDTH // 2, 25, center=True)
    display_connection_status()
    panel_buffers[4].dirty = True
    commit_buffers()
    time.sleep(2)
    
    # **NEW: Show "NEW ROUND BEGINS" animation**
    print("Starting new round animation...")
    new_round_animation_enhanced()
    
    # Reset for new round with proper dealer rotation
    game_state['dealer'] = (game_state['dealer'] - 1) % 4  # Anti-clockwise
    game_state['trump_selector'] = (game_state['dealer'] + 1) % 4  # Dealer's RIGHT
    
    # Deal new cards
    deck = create_deck()
    hands = deal_cards(deck)
    selected_indices = [0, 0, 0, 0]
    
    # Reset all game state variables
    game_state['phase'] = 'trump_selection'
    game_state['trump_suit'] = None
    game_state['trump_team'] = None
    game_state['current_trick'] = [None, None, None, None]
    game_state['tricks_won'] = {'A': 0, 'B': 0}
    game_state['active_players'] = [0, 1, 2, 3]
    
    # Reset half court and full court modes
    game_state['half_court_mode'] = False
    game_state['half_court_player'] = None
    game_state['half_court_team'] = None
    game_state['full_court_mode'] = False
    game_state['full_court_player'] = None
    game_state['full_court_team'] = None
    game_state['first_trick_started'] = False
    game_state['trick_leader'] = None
    
    # FIXED: Clear ALL scanning-related flags
    game_state['scanning_active'] = False
    game_state['scanning_just_completed'] = False
    game_state['show_scan_ready'] = False
    game_state['show_scans_left'] = False
    
    # Increment round number
    game_state['round_number'] = game_state.get('round_number', 1) + 1
    
    # Clear all panels
    clear_all_panels()
    
    # Show trump selection prompt
    clear_panel(4)
    draw_text_enhanced_fixed(4, f"Player {game_state['trump_selector'] + 1}", YELLOW, PANEL_WIDTH // 2, 10, center=True)
    draw_text_enhanced_fixed(4, "Select Trump", WHITE, PANEL_WIDTH // 2, 20, center=True)
    display_connection_status()
    panel_buffers[4].dirty = True
    commit_buffers()
    
    print(f"New round {game_state['round_number']}: Dealer is Player {game_state['dealer'] + 1}, Trump selector is Player {game_state['trump_selector'] + 1}")
    
    return True

def reset_for_new_round():
    """Reset game state for new round"""
    global hands, remaining_cards
    
    # Deal new cards
    hands, remaining_cards = deal_cards_with_half_court()
    selected_indices = [0, 0, 0, 0]
    
    # Reset game state
    game_state['dealer'] = (game_state.get('dealer', 0) + 3) % 4
    game_state['trump_selector'] = (game_state['dealer'] + 3) % 4
    game_state['phase'] = 'trump_selection'
    game_state['trump_suit'] = None
    game_state['trump_team'] = None
    
    # Reset half court state
    game_state['half_court_mode'] = False
    game_state['half_court_player'] = None
    game_state['half_court_team'] = None
    game_state['active_players'] = [0, 1, 2, 3]
    game_state['first_four_cards_dealt'] = False
    
    # Reset scores
    game_state['tricks_won'] = {'A': 0, 'B': 0}
    game_state['current_round'] = game_state.get('current_round', 1) + 1
    
    print(f"Starting new round {game_state['current_round']}")
    return game_state['trump_selector']

def get_next_active_player(current_player, active_players):
    """Get the next active player in ANTI-CLOCKWISE sequence"""
    if current_player not in active_players:
        return active_players[0]  # Start with first active player
    
    current_index = active_players.index(current_player)
    # CRITICAL FIX: Anti-clockwise means going backwards in the list
    next_index = (current_index - 1) % len(active_players)
    return active_players[next_index]

def get_next_player_anticlockwise(current_player):
    """Get next player in anti-clockwise order (0?3?2?1?0)"""
    return (current_player - 1) % 4

def is_player_active(player):
    """Check if a player is active in current game mode"""
    return player in game_state.get('active_players', [0, 1, 2, 3])

def calculate_perfect_text_metrics(text, panel_width=PANEL_WIDTH, max_char_width=14):
    """Calculate perfect spacing for text to fit optimally in panel"""
    if not text:
        return 0, 0, 0
    
    text_length = len(text)
    
    # Available width (leave small margins)
    available_width = panel_width - 4
    
    # Calculate optimal character width and spacing
    if text_length <= 3:
        char_width = min(max_char_width, available_width // text_length)
        char_spacing = 2
    elif text_length <= 5:
        char_width = min(12, available_width // text_length)
        char_spacing = 1
    elif text_length <= 8:
        char_width = min(10, available_width // text_length)
        char_spacing = 1
    else:
        char_width = min(8, available_width // text_length)
        char_spacing = 0
    
    # Calculate total text width
    total_width = (text_length * char_width) + ((text_length - 1) * char_spacing)
    
    # Center position
    start_x = max(2, (panel_width - total_width) // 2)
    
    return char_width, char_spacing, start_x

def draw_perfect_text(panel_num, text, color, y, center_x=None, char_height=8):
    """Draw text with PERFECT spacing, centering, and readability"""
    if not text:
        return
    
    buffer = panel_buffers[panel_num].back_buffer
    
    # Calculate perfect metrics
    char_width, char_spacing, start_x = calculate_perfect_text_metrics(text.upper())
    
    # Override start position if center_x is provided
    if center_x is not None:
        total_width = (len(text) * char_width) + ((len(text) - 1) * char_spacing)
        start_x = max(2, center_x - (total_width // 2))
    
    current_x = start_x
    
    for char in text.upper():
        if char == ' ':
            current_x += char_width + char_spacing
            continue
            
        pattern = get_perfect_letter_pattern(char)
        if not pattern:
            current_x += char_width + char_spacing
            continue
        
        # Ensure we don't exceed panel bounds
        if current_x + char_width > PANEL_WIDTH - 2:
            break
        
        # Draw character with perfect scaling
        for row_idx, row in enumerate(pattern[:char_height]):
            if y + row_idx >= PANEL_HEIGHT:
                break
                
            for col_idx in range(min(char_width, len(row))):
                if col_idx < len(row) and row[col_idx] == '1':
                    px = current_x + col_idx
                    py = y + row_idx
                    
                    if 0 <= px < PANEL_WIDTH and 0 <= py < PANEL_HEIGHT:
                        buffer[py][px] = color
        
        current_x += char_width + char_spacing
    
    panel_buffers[panel_num].dirty = True

def draw_spectacular_text(panel_num, text, base_color, y, effects=None):
    """Draw text with spectacular visual effects"""
    if effects is None:
        effects = {}
    
    # Apply pulsing effect
    if effects.get('pulse', False):
        pulse_factor = (math.sin(time.time() * 3) + 1) / 2
        brightness = int(150 + (105 * pulse_factor))
        color = (
            min(255, int(base_color[0] * brightness / 255)),
            min(255, int(base_color[1] * brightness / 255)), 
            min(255, int(base_color[2] * brightness / 255))
        )
    else:
        color = base_color
    
    # Apply shadow effect
    if effects.get('shadow', False):
        shadow_color = (
            max(0, color[0] // 4),
            max(0, color[1] // 4),
            max(0, color[2] // 4)
        )
        draw_perfect_text(panel_num, text, shadow_color, y + 1)
    
    # Apply glow effect
    if effects.get('glow', False):
        glow_color = (
            min(255, color[0] + 50),
            min(255, color[1] + 50),
            min(255, color[2] + 50)
        )
        # Draw glow around main text
        for offset_x in [-1, 0, 1]:
            for offset_y in [-1, 0, 1]:
                if offset_x != 0 or offset_y != 0:
                    draw_perfect_text(panel_num, text, glow_color, y + offset_y)
    
    # Draw main text
    draw_perfect_text(panel_num, text, color, y)

def create_particle_burst(center_x, center_y, count=20, colors=None):
    """Create spectacular particle burst effect"""
    if colors is None:
        colors = [WHITE, YELLOW, CYAN, MAGENTA, ORANGE]
    
    particles = []
    for _ in range(count):
        angle = random.uniform(0, 2 * math.pi)
        speed = random.uniform(0.5, 2.0)
        color = random.choice(colors)
        particles.append({
            'x': center_x,
            'y': center_y,
            'vx': math.cos(angle) * speed,
            'vy': math.sin(angle) * speed,
            'color': color,
            'life': 1.0
        })
    return particles

def update_particles(particles, dt=0.033):
    """Update particle positions and life"""
    for particle in particles[:]:
        particle['x'] += particle['vx']
        particle['y'] += particle['vy']
        particle['life'] -= dt * 2  # Fade over time
        
        if particle['life'] <= 0:
            particles.remove(particle)

def draw_particles(panel_num, particles):
    """Draw particles with fading effect"""
    buffer = panel_buffers[panel_num].back_buffer
    
    for particle in particles:
        x, y = int(particle['x']), int(particle['y'])
        if 0 <= x < PANEL_WIDTH and 0 <= y < PANEL_HEIGHT:
            # Apply fading based on life
            alpha = max(0, particle['life'])
            color = tuple(int(c * alpha) for c in particle['color'])
            buffer[y][x] = color

def create_rainbow_wave(frame, width=PANEL_WIDTH, height=PANEL_HEIGHT):
    """Create rainbow wave background effect"""
    wave_data = []
    for y in range(height):
        row = []
        for x in range(width):
            # Create wave pattern
            wave = math.sin((x + frame * 0.1) * 0.2) + math.sin((y + frame * 0.15) * 0.15)
            hue = (wave + 2) / 4 * 360  # Convert to hue (0-360)
            
            # Convert HSV to RGB
            hue = hue % 360
            if hue < 60:
                r, g, b = 255, int(255 * hue / 60), 0
            elif hue < 120:
                r, g, b = int(255 * (120 - hue) / 60), 255, 0
            elif hue < 180:
                r, g, b = 0, 255, int(255 * (hue - 120) / 60)
            elif hue < 240:
                r, g, b = 0, int(255 * (240 - hue) / 60), 255
            elif hue < 300:
                r, g, b = int(255 * (hue - 240) / 60), 0, 255
            else:
                r, g, b = 255, 0, int(255 * (360 - hue) / 60)
            
            # Dim the background
            row.append((r // 4, g // 4, b // 4))
        wave_data.append(row)
    return wave_data

def team_won_round_animation_enhanced(winning_team):
    """Enhanced team won animation with effects"""
    text = f"TEAM {winning_team} WON THE ROUND"
    team_color = GREEN if winning_team == 'A' else BLUE
    
    # Celebration effect with expanding rings
    for frame in range(60):
        clear_panel(4)
        
        # Draw expanding celebration rings
        center_x, center_y = PANEL_WIDTH // 2, PANEL_HEIGHT // 2
        for ring in range(3):
            radius = (frame + ring * 10) % 30
            if radius < 25:
                for angle in range(0, 360, 15):
                    x = center_x + int(radius * math.cos(math.radians(angle)))
                    y = center_y + int(radius * math.sin(math.radians(angle)))
                    if 0 <= x < PANEL_WIDTH and 0 <= y < PANEL_HEIGHT:
                        alpha = 1 - (radius / 25)
                        color = (int(team_color[0] * alpha), int(team_color[1] * alpha), int(team_color[2] * alpha))
                        panel_buffers[4].back_buffer[y][x] = color
        
        # Draw pulsing text
        draw_pulsing_text_enhanced(4, text, team_color, frame)
        update_display()
        time.sleep(0.05)
    
    time.sleep(1)

# Updated for Omi - Deal 32 cards with A-K-Q-J-10-9-8-7
def deal_cards_with_half_court():
    """Deal cards with half court support - first 4 cards, then option, then remaining 4"""
    deck = [(suit, rank) for suit in SUITS for rank in RANKS]
    random.shuffle(deck)
    
    hands = [[], [], [], []]
    
    # Deal first 4 cards to each player
    for i in range(4):
        for player in range(4):
            hands[player].append(deck[i * 4 + player])
    
    game_state['first_four_cards_dealt'] = True
    return hands, deck[16:]  # Return hands and remaining cards

def welcome_animation_enhanced():
    """Spectacular welcome animation with perfect text"""
    particles = []
    
    for frame in range(120):
        clear_panel(4)
        
        # Create rainbow background wave
        wave_bg = create_rainbow_wave(frame)
        for y in range(PANEL_HEIGHT):
            for x in range(PANEL_WIDTH):
                panel_buffers[4].back_buffer[y][x] = wave_bg[y][x]
        
        # Add particle bursts periodically
        if frame % 15 == 0:
            particles.extend(create_particle_burst(
                random.randint(10, PANEL_WIDTH-10),
                random.randint(10, PANEL_HEIGHT-10),
                count=8, colors=[WHITE, YELLOW, CYAN, PINK]
            ))
        
        # Update and draw particles
        update_particles(particles)
        draw_particles(4, particles)
        
        # Draw spectacular welcome text
        effects = {'pulse': True, 'glow': True, 'shadow': True}
        draw_spectacular_text(4, "WELCOME", CYAN, 12, effects)
        draw_spectacular_text(4, "TO OMI", YELLOW, 24, effects)
        draw_spectacular_text(4, "GAME", MAGENTA, 36, effects)
        
        # Add extra sparkles
        for _ in range(8):
            x = random.randint(0, PANEL_WIDTH - 1)
            y = random.randint(0, PANEL_HEIGHT - 1)
            if random.random() > 0.7:
                panel_buffers[4].back_buffer[y][x] = WHITE
        
        panel_buffers[4].dirty = True
        commit_buffers()
        time.sleep(0.033)
    
    time.sleep(2)

def loading_phase_enhanced():
    """Enhanced loading phase - KEEPING ORIGINAL NAME"""
    while game_state['progress'] < 100:
        clear_panel(4)
        draw_perfect_text(4, "LOADING", WHITE, 20)
        draw_progress_bar_enhanced(4, game_state['progress'])
        commit_buffers()
        game_state['progress'] += 1
        time.sleep(0.05)

def get_non_trump_team_players():
    """Get players from the team that didn't select trump"""
    trump_team = game_state['trump_team']
    non_trump_team = 'B' if trump_team == 'A' else 'A'
    return TEAMS[non_trump_team]

def is_half_court_eligible():
    """Check if half court option is available"""
    return (game_state['first_four_cards_dealt'] and 
            not game_state['half_court_mode'] and 
            game_state['phase'] == 'half_court_option')

def setup_half_court_game_fixed(half_court_player):
    """Setup half court game with correct player management"""
    game_state['half_court_mode'] = True
    game_state['half_court_player'] = half_court_player
    game_state['half_court_team'] = get_team_for_player(half_court_player)
    
    # Get trump team players
    trump_team_players = TEAMS[game_state['trump_team']]
    
    # Active players: half court player + both trump team players
    game_state['active_players'] = [half_court_player] + trump_team_players
    
    # Remove duplicates if half court player is somehow in trump team
    game_state['active_players'] = list(set(game_state['active_players']))
    
    print(f"Half court mode activated!")
    print(f"Half court player: Player {half_court_player + 1} (Team {game_state['half_court_team']})")
    print(f"Trump team: Team {game_state['trump_team']}")
    print(f"Active players: {[p + 1 for p in game_state['active_players']]}")
    
    return game_state['active_players']

def check_half_court_winner():
    """Check winner in half court mode"""
    if not game_state['half_court_mode']:
        return None
    
    half_court_player = game_state['half_court_player']
    half_court_team = game_state['half_court_team']
    trump_team = game_state['trump_team']
    
    # Half court player needs all 4 tricks to win
    if game_state['tricks_won'][half_court_team] == 4:
        return half_court_player, True  # Half court player wins
    elif game_state['tricks_won'][trump_team] >= 1:
        return trump_team, False  # Trump team wins (half court player lost)
    
    return None

def apply_half_court_tokens(winner, is_half_court_win):
    """Apply token changes for half court result"""
    if is_half_court_win:
        # Half court player wins - trump team loses 2 tokens
        half_court_team = game_state['half_court_team']
        trump_team = game_state['trump_team']
        game_state['team_tokens'][trump_team] -= 2
        print(f"Half court player wins! Team {trump_team} loses 2 tokens!")
        print(f"Tokens now - Team A: {game_state['team_tokens']['A']}, Team B: {game_state['team_tokens']['B']}")
    else:
        # Half court player loses - half court team loses 2 tokens
        half_court_team = game_state['half_court_team']
        trump_team = game_state['trump_team']
        game_state['team_tokens'][half_court_team] -= 2
        print(f"Half court player loses! Team {half_court_team} loses 2 tokens!")
        print(f"Tokens now - Team A: {game_state['team_tokens']['A']}, Team B: {game_state['team_tokens']['B']}")

def complete_reset_after_half_court():
    """Complete game reset with ANTI-CLOCKWISE dealer rotation"""
    print("=== COMPLETE RESET AFTER HALF COURT ===")
    
    # CRITICAL FIX: Anti-clockwise dealer rotation
    game_state['dealer'] = (game_state.get('dealer', 0) - 1) % 4  # Changed from +3 to -1
    game_state['trump_selector'] = (game_state['dealer'] - 1) % 4  # Anti-clockwise from dealer
    
    # Reset ALL game state variables
    game_state['phase'] = 'trump_selection'
    game_state['display_mode'] = 'normal'
    game_state['trump_suit'] = None
    game_state['trump_team'] = None
    game_state['current_trick'] = [None, None, None, None]
    game_state['trick_leader'] = None
    game_state['tricks_won'] = {'A': 0, 'B': 0}
    
    # Reset half court state completely
    game_state['half_court_mode'] = False
    game_state['half_court_player'] = None
    game_state['half_court_team'] = None
    game_state['active_players'] = [0, 1, 2, 3]
    game_state['first_four_cards_dealt'] = False
    game_state['first_four_display'] = []
    game_state['half_court_timer'] = 0
    
    game_state['current_round'] = game_state.get('current_round', 1) + 1
    
    print(f"New match {game_state['current_round']} starting")
    print(f"New dealer: Player {game_state['dealer'] + 1}")
    print(f"New trump selector: Player {game_state['trump_selector'] + 1}")
    
    return game_state['trump_selector']

def update_display_optimized():
    """Optimized display update that minimizes flickering"""
    # Only commit buffers that are actually dirty
    dirty_panels = []
    for panel_num in range(PANEL_COUNT):
        if panel_buffers[panel_num].dirty:
            dirty_panels.append(panel_num)
            x_offset = panel_num * PANEL_WIDTH
            buffer = panel_buffers[panel_num].front_buffer
            for y in range(PANEL_HEIGHT):
                for x in range(PANEL_WIDTH):
                    matrix.SetPixel(x_offset + x, y, *buffer[y][x])
            panel_buffers[panel_num].swap()
    
    if dirty_panels:
        print(f"Updated panels: {dirty_panels}")


def lets_begin_phase_enhanced():
    """Enhanced LETS BEGIN phase"""
    for frame in range(90):
        if frame % 2 == 0:
            clear_panel(4)
            
            # Add excitement effects
            if frame % 10 == 0:
                for _ in range(3):
                    x = random.randint(0, PANEL_WIDTH - 1)
                    y = random.randint(0, PANEL_HEIGHT - 1)
                    panel_buffers[4].back_buffer[y][x] = YELLOW
            
            draw_pulsing_text_enhanced(4, "LETS BEGIN", GREEN, frame)
            update_display()
        time.sleep(0.033)

def trump_selected_phase_enhanced():
    """Enhanced trump selection display with announcement and realistic movement"""
    # Phase 1: Trump announcement animation
    trump_announcement_animation_enhanced(game_state['trump_suit'])
    
    # Phase 2: Realistic movement animation to corner
    animate_trump_to_corner_enhanced_realistic(game_state['trump_suit'])

def giving_cards_phase_enhanced():
    """Enhanced giving cards animation"""
    for frame in range(60):
        if frame % 2 == 0:
            clear_panel(4)
            
            # Add card dealing effect
            for i in range(4):
                if frame > i * 10:
                    x = 10 + i * 12
                    y = 25 + int(5 * math.sin(frame * 0.2 + i))
                    for dy in range(8):
                        for dx in range(6):
                            if 0 <= x + dx < PANEL_WIDTH and 0 <= y + dy < PANEL_HEIGHT:
                                panel_buffers[4].back_buffer[y + dy][x + dx] = WHITE
            
            # Fixed GIVING CARDS text display - force it to split into two lines
            draw_text_enhanced(4, "GIVING", YELLOW, PANEL_WIDTH // 2, 45, center=True, letter_spacing=1)
            draw_text_enhanced(4, "CARDS", YELLOW, PANEL_WIDTH // 2, 55, center=True, letter_spacing=1)
            update_display()
        time.sleep(0.033)

def display_last_trick_cards_corrected(cards, requesting_player):
    """**CORRECTED LAST TRICK DISPLAY** using your existing symbol system"""
    if not cards or all(c is None for c in cards):
        clear_panel(4)
        draw_text_enhanced_fixed(4, "NO PREVIOUS", WHITE, PANEL_WIDTH // 2, 25, center=True)
        draw_text_enhanced_fixed(4, "TRICK", WHITE, PANEL_WIDTH // 2, 35, center=True)
        panel_buffers[4].dirty = True
        commit_buffers()
        time.sleep(2)
        return
    
    # Display for 6 seconds using your existing symbol system
    for frame in range(180):  # 6 seconds at 0.033s per frame
        clear_panel(4)
        
        # Draw borders
        border_color = (100, 100, 100)
        # Outer border
        for x in range(PANEL_WIDTH):
            panel_buffers[4].back_buffer[0][x] = border_color
            panel_buffers[4].back_buffer[PANEL_HEIGHT - 1][x] = border_color
        for y in range(PANEL_HEIGHT):
            panel_buffers[4].back_buffer[y][0] = border_color
            panel_buffers[4].back_buffer[y][PANEL_WIDTH - 1] = border_color
        
        # Center dividing lines
        center_x, center_y = PANEL_WIDTH // 2, PANEL_HEIGHT // 2
        for x in range(1, PANEL_WIDTH - 1):
            panel_buffers[4].back_buffer[center_y][x] = border_color
        for y in range(1, PANEL_HEIGHT - 1):
            panel_buffers[4].back_buffer[y][center_x] = border_color
        
        # 32x32 quadrant positions
        quadrants = [
            (2, 2),    # Top-left (32x32)
            (34, 2),   # Top-right (32x32)
            (2, 34),   # Bottom-left (32x32)
            (34, 34)   # Bottom-right (32x32)
        ]
        
        # Player order based on requesting player
        player_order = [(requesting_player + i) % 4 for i in range(4)]
        
        for idx, player_pos in enumerate(player_order):
            if player_pos < len(cards) and cards[player_pos] is not None:
                card = cards[player_pos]
                qx, qy = quadrants[idx]
                
                # **USE YOUR EXISTING SYMBOLS AND RANK_PATTERNS**
                suit_color = SUIT_COLORS[card[0]]  # Use your existing color mapping
                rank_color = WHITE
                
                # Draw small P# label (reduced size to fit)
                player_label = f"P{player_pos + 1}"
                draw_text_enhanced_fixed(4, player_label, CYAN, qx + 16, qy + 2, center=True)
                
                # **DRAW SUIT USING YOUR EXISTING symbols DICTIONARY**
                if card[0] in symbols:
                    symbol_data = symbols[card[0]]
                    suit_x = qx + 8  # Centered in 32x32 quadrant
                    suit_y = qy + 8
                    
                    # Draw with 1.5x scale for better visibility
                    for y, row in enumerate(symbol_data[:12]):  # Use first 12 rows
                        for x, pixel in enumerate(row[:12]):    # Use first 12 cols
                            if pixel == '1':
                                # Draw 1.5x scale (rounded to pixels)
                                for sy in range(2):  # 1.5x ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¾ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Â¦Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Â¦Ãƒâ€šÃ‚Â¾ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Â¦Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¾ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¾ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¦ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Â¦Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â¦ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Â¦Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¾ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Â¦Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Â¦Ãƒâ€šÃ‚Â¾ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Â¦Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â¦ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Â¦Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¾ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Â¦Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Â¦Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Â¦Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â¦ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Â¦Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¦ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Â¦Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Â¦Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â¦ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Â¦Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¾ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¦ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Â¦Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â¦ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Â¦Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â°ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¾ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Â¦Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Â¦Ãƒâ€šÃ‚Â¾ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Â¦Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Â¦Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â¦ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Â¦Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Â¦Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¹ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¾ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Â¦Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Â¦Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¦ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Â¦Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¾Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Â¦Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â¦ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Â ÃƒÂ¢Ã¢â€šÂ¬Ã¢â€žÂ¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Â¦Ãƒâ€šÃ‚Â¡ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€¦Ã‚Â¡ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â  2x for pixels
                                    for sx in range(2):
                                        px = suit_x + x + sx
                                        py = suit_y + y + sy
                                        if qx < px < qx + 30 and qy < py < qy + 30:  # Keep within quadrant
                                            if 0 <= px < PANEL_WIDTH and 0 <= py < PANEL_HEIGHT:
                                                panel_buffers[4].back_buffer[py][px] = suit_color
                
                # **DRAW RANK USING YOUR EXISTING rank_patterns DICTIONARY**
                if card[1] in rank_patterns:
                    rank_data = rank_patterns[card[1]]
                    rank_x = qx + 8   # Centered in 32x32 quadrant
                    rank_y = qy + 20  # Below the suit
                    
                    # Draw with 1.5x scale for better visibility
                    for y, row in enumerate(rank_data[:8]):   # Use first 8 rows
                        for x, pixel in enumerate(row[:12]):  # Use first 12 cols
                            if pixel == '1':
                                # Draw 1.5x scale (rounded to pixels)
                                for sy in range(2):
                                    for sx in range(2):
                                        px = rank_x + x + sx
                                        py = rank_y + y + sy
                                        if qx < px < qx + 30 and qy < py < qy + 30:  # Keep within quadrant
                                            if 0 <= px < PANEL_WIDTH and 0 <= py < PANEL_HEIGHT:
                                                panel_buffers[4].back_buffer[py][px] = rank_color
        
        panel_buffers[4].dirty = True
        commit_buffers()
        time.sleep(0.033)

def display_canceled_cards_corrected(cards):
    """**CORRECTED CANCELED CARDS DISPLAY** using your existing symbol system"""
    for frame in range(90):  # 3 seconds
        clear_panel(4)
        
        # Pulsing golden border
        pulse = (math.sin(frame * 0.3) + 1) / 2
        border_brightness = int(100 + (155 * pulse))
        border_color = (border_brightness, border_brightness, 0)
        
        # Thick border
        for t in range(3):
            for x in range(t, PANEL_WIDTH - t):
                panel_buffers[4].back_buffer[t][x] = border_color
                panel_buffers[4].back_buffer[PANEL_HEIGHT - 1 - t][x] = border_color
            for y in range(t, PANEL_HEIGHT - t):
                panel_buffers[4].back_buffer[y][t] = border_color
                panel_buffers[4].back_buffer[y][PANEL_WIDTH - 1 - t] = border_color
        
        # Center dividing lines
        center_x, center_y = PANEL_WIDTH // 2, PANEL_HEIGHT // 2
        for x in range(3, PANEL_WIDTH - 3):
            panel_buffers[4].back_buffer[center_y][x] = border_color
        for y in range(3, PANEL_HEIGHT - 3):
            panel_buffers[4].back_buffer[y][center_x] = border_color
        
        # Card positions in quadrants
        quadrants = [(4, 4), (36, 4), (4, 36), (36, 36)]
        
        for idx, card in enumerate(cards[:4]):
            if card is not None:
                qx, qy = quadrants[idx]
                
                # Card colors
                suit_color = SUIT_COLORS[card[0]]  # Use your existing colors
                if card[0] in ['hearts', 'diamonds']:
                    suit_color = (255, 150, 150)  # Lighter for canceled cards
                else:
                    suit_color = (200, 200, 200)
                rank_color = WHITE
                
                # **DRAW SUIT USING YOUR EXISTING symbols DICTIONARY**
                if card[0] in symbols:
                    symbol_data = symbols[card[0]]
                    suit_x = qx + 10
                    suit_y = qy + 6
                    
                    # Draw with 2x scale
                    for y, row in enumerate(symbol_data[:10]):
                        for x, pixel in enumerate(row[:10]):
                            if pixel == '1':
                                for sy in range(2):
                                    for sx in range(2):
                                        px = suit_x + x * 2 + sx
                                        py = suit_y + y * 2 + sy
                                        if 0 <= px < PANEL_WIDTH and 0 <= py < PANEL_HEIGHT:
                                            panel_buffers[4].back_buffer[py][px] = suit_color
                
                # **DRAW RANK USING YOUR EXISTING rank_patterns DICTIONARY**
                if card[1] in rank_patterns:
                    rank_data = rank_patterns[card[1]]
                    rank_x = qx + 10
                    rank_y = qy + 26
                    
                    # Draw with 1x scale (smaller for canceled display)
                    for y, row in enumerate(rank_data[:6]):
                        for x, pixel in enumerate(row[:10]):
                            if pixel == '1':
                                px = rank_x + x
                                py = rank_y + y
                                if 0 <= px < PANEL_WIDTH and 0 <= py < PANEL_HEIGHT:
                                    panel_buffers[4].back_buffer[py][px] = rank_color
        
        # Sparkle effects
        for _ in range(12):
            sx = random.randint(5, PANEL_WIDTH - 5)
            sy = random.randint(5, PANEL_HEIGHT - 5)
            if random.random() > 0.6:
                panel_buffers[4].back_buffer[sy][sx] = WHITE
        
        panel_buffers[4].dirty = True
        commit_buffers()
        time.sleep(0.033)
    
    time.sleep(1)

def show_invalid_cancel_warning_fixed():
    """Display warning when player tries to cancel trump but cards are not all <= 10"""
    print("Invalid trump cancel attempt - not all cards are 10 or below!")
    
    # Optional: Display a visual warning on the main panel
    clear_panel(4)
    
    # Draw warning message
    draw_text_enhanced_fixed(4, "INVALID", RED, PANEL_WIDTH // 2, 15, center=True)
    draw_text_enhanced_fixed(4, "CANCEL", RED, PANEL_WIDTH // 2, 25, center=True)
    draw_text_enhanced_fixed(4, "CARDS NOT", WHITE, PANEL_WIDTH // 2, 35, center=True)
    draw_text_enhanced_fixed(4, "ALL <= 10", WHITE, PANEL_WIDTH // 2, 45, center=True)
    
    panel_buffers[4].dirty = True
    commit_buffers()
    
    # Show warning for 2 seconds
    time.sleep(2)
    
    # Clear the warning
    clear_panel(4)
    panel_buffers[4].dirty = True
    commit_buffers()

def show_invalid_cancel_warning_corrected():
    """Enhanced multiline warning with better text layout"""
    for frame in range(120):  # 4 seconds
        clear_panel(4)
        
        # Flashing background
        flash = (frame // 15) % 2
        bg_color = (80, 0, 0) if flash else (0, 0, 0)
        text_color = WHITE if flash else YELLOW
        
        # Fill background
        if flash:
            for y in range(PANEL_HEIGHT):
                for x in range(PANEL_WIDTH):
                    panel_buffers[4].back_buffer[y][x] = bg_color
        
        # **PROPERLY SPACED WARNING TEXT**
        draw_text_enhanced_fixed(4, "CARDS", text_color, PANEL_WIDTH // 2, 8, center=True)
        draw_text_enhanced_fixed(4, "ARE", text_color, PANEL_WIDTH // 2, 18, center=True)
        draw_text_enhanced_fixed(4, "NOT", text_color, PANEL_WIDTH // 2, 28, center=True)
        draw_text_enhanced_fixed(4, "UNDER", text_color, PANEL_WIDTH // 2, 38, center=True)
        draw_text_enhanced_fixed(4, "10!!", text_color, PANEL_WIDTH // 2, 48, center=True)
        
        # Warning symbols in corners
        if flash:
            corner_color = RED
            draw_text_enhanced_fixed(4, "!", corner_color, 8, 8, center=False)
            draw_text_enhanced_fixed(4, "!", corner_color, PANEL_WIDTH - 8, 8, center=False)
            draw_text_enhanced_fixed(4, "!", corner_color, 8, PANEL_HEIGHT - 16, center=False)
            draw_text_enhanced_fixed(4, "!", corner_color, PANEL_WIDTH - 8, PANEL_HEIGHT - 16, center=False)
        
        panel_buffers[4].dirty = True
        commit_buffers()
        time.sleep(0.033)
    
    time.sleep(1)

def start_phase_enhanced():
    """Enhanced start phase"""
    for frame in range(60):
        if frame % 2 == 0:
            clear_panel(4)
            
            # Add countdown effect
            if frame < 20:
                draw_text_enhanced(4, "3", RED, PANEL_WIDTH // 2, PANEL_HEIGHT // 2, center=True, scale=2)
            elif frame < 40:
                draw_text_enhanced(4, "2", YELLOW, PANEL_WIDTH // 2, PANEL_HEIGHT // 2, center=True, scale=2)
            elif frame < 60:
                draw_text_enhanced(4, "1", GREEN, PANEL_WIDTH // 2, PANEL_HEIGHT // 2, center=True, scale=2)
            
            update_display()
        time.sleep(0.033)
    
    # Final START message
    for frame in range(30):
        if frame % 2 == 0:
            clear_panel(4)
            draw_pulsing_text_enhanced(4, "START", GREEN, frame)
            update_display()
        time.sleep(0.033)

def display_text_animation_enhanced(text, color, duration):
    """Enhanced text animation with effects"""
    for frame in range(duration * 30):
        if frame % 2 == 0:
            clear_panel(4)
            
            # Add background effects
            for _ in range(2):
                x = random.randint(0, PANEL_WIDTH - 1)
                y = random.randint(0, PANEL_HEIGHT - 1)
                if panel_buffers[4].back_buffer[y][x] == BLACK:
                    panel_buffers[4].back_buffer[y][x] = (color[0] // 4, color[1] // 4, color[2] // 4)
            
            brightness = int(255 * (0.6 + 0.4 * math.sin(frame * 0.2)))
            pulse_color = (color[0] * brightness // 255, color[1] * brightness // 255, color[2] * brightness // 255)
            
            draw_multiline_text_enhanced(4, text, pulse_color)
            update_display()
        
        time.sleep(0.033)

def display_trump_selection_phase_enhanced(hands, trump_selector, selected_index):
    """Enhanced trump selection interface - Updated for Omi with trump cancel support"""
    clear_all_panels()
    
    # Main panel - enhanced trump selection display
    draw_text_enhanced(4, "SELECT", WHITE, PANEL_WIDTH // 2, 5, center=True, letter_spacing=1)
    draw_text_enhanced(4, "TRUMP", YELLOW, PANEL_WIDTH // 2, 15, center=True, letter_spacing=1)

    # Draw suits under the text
    draw_trump_selection_suits_enhanced(4)
    
    # Show only trump selector's first 4 cards with enhanced selection
    for i in range(4):
        if i < len(hands[trump_selector]):
            card = hands[trump_selector][i]
            pos = CARD_POSITIONS[i]
            draw_card(trump_selector, pos[0], pos[1], card, selected=(i == selected_index))
    
    # **FIXED: Show UP=CANCEL hint only when eligible**
    if (hands and 
        all_cards_10_or_below_fixed(hands[trump_selector][:4]) and 
        selected_index == 0):  # Must be at position 0 (top-left card)
        draw_text_enhanced_fixed(4, "UP=CANCEL", GREEN, 2, 58, center=False)
        panel_buffers[4].dirty = True
    
    update_display()

def display_instruction_text_enhanced(instruction):
    """Enhanced instruction display"""
    clear_panel(4)
    draw_multiline_text_enhanced(4, instruction, CYAN, line_spacing=3)
    update_display()

def winner_animation_enhanced(winning_team):
    """Enhanced winner animation with spectacular effects"""
    team_color = GREEN if winning_team == 'A' else BLUE
    
    # Fireworks effect
    for frame in range(120):
        if frame % 2 == 0:
            clear_panel(4)
            
            # Multiple expanding circles
            center_x, center_y = PANEL_WIDTH // 2, PANEL_HEIGHT // 2
            for explosion in range(3):
                radius = (frame + explosion * 20) % 40
                if radius < 30:
                    for angle in range(0, 360, 10):
                        x = center_x + int(radius * math.cos(math.radians(angle)))
                        y = center_y + int(radius * math.sin(math.radians(angle)))
                        if 0 <= x < PANEL_WIDTH and 0 <= y < PANEL_HEIGHT:
                            alpha = 1 - (radius / 30)
                            color = (int(team_color[0] * alpha), int(team_color[1] * alpha), int(team_color[2] * alpha))
                            panel_buffers[4].back_buffer[y][x] = color
            
            # Sparkles
            for _ in range(8):
                x = random.randint(0, PANEL_WIDTH - 1)
                y = random.randint(0, PANEL_HEIGHT - 1)
                if random.random() > 0.7:
                    panel_buffers[4].back_buffer[y][x] = WHITE
            
            update_display()
        time.sleep(0.05)
    
    # Display winner text
    winner_text = f"TEAM {winning_team} WINS"
    display_text_animation_enhanced(winner_text, team_color, 3)

def display_trick_winner_animation(winner_player, winning_team, duration=4):
    """Enhanced trick winner animation with multiple phases"""
    team_color = GREEN if winning_team == 'A' else BLUE
    winner_text = f"TEAM {winning_team} PLAYER {winner_player + 1} WON"
    
    # Phase 1: Build-up animation (1 second)
    for frame in range(30):
        clear_panel(4)
        
        # Growing circle effect
        radius = frame
        center_x, center_y = PANEL_WIDTH // 2, PANEL_HEIGHT // 2
        for angle in range(0, 360, 15):
            x = center_x + int(radius * math.cos(math.radians(angle)))
            y = center_y + int(radius * math.sin(math.radians(angle)))
            if 0 <= x < PANEL_WIDTH and 0 <= y < PANEL_HEIGHT:
                panel_buffers[4].back_buffer[y][x] = team_color
        
        panel_buffers[4].dirty = True
        update_display()
        time.sleep(0.033)
    
    # Phase 2: Winner text display with celebration (3 seconds)
    for frame in range(90):
        clear_panel(4)
        
        # Celebration effects
        for ring in range(3):
            radius = (frame + ring * 20) % 30
            if radius < 25:
                for angle in range(0, 360, 12):
                    x = center_x + int(radius * math.cos(math.radians(angle)))
                    y = center_y + int(radius * math.sin(math.radians(angle)))
                    if 0 <= x < PANEL_WIDTH and 0 <= y < PANEL_HEIGHT:
                        alpha = 1 - (radius / 25)
                        color = (int(team_color[0] * alpha), int(team_color[1] * alpha), int(team_color[2] * alpha))
                        panel_buffers[4].back_buffer[y][x] = color
        
        # Random sparkles
        for _ in range(5):
            x = random.randint(0, PANEL_WIDTH - 1)
            y = random.randint(0, PANEL_HEIGHT - 1)
            if random.random() > 0.6:
                panel_buffers[4].back_buffer[y][x] = WHITE
        
        # Pulsing text
        draw_pulsing_text_enhanced(4, winner_text, team_color, frame)
        
        panel_buffers[4].dirty = True
        update_display()
        time.sleep(0.033)

def display_half_court_confirmation(player_name):
    """Display half court confirmation with properly positioned YES/NO options"""
    clear_panel(4)
    
    # Player identification - top of panel
    draw_text_enhanced(4, f"P{player_name + 1}", WHITE, PANEL_WIDTH // 2, 3, center=True, letter_spacing=1)
    
    # Question text - middle section
    draw_text_enhanced(4, "HALF", YELLOW, PANEL_WIDTH // 2, 15, center=True, letter_spacing=1)
    draw_text_enhanced(4, "COURT?", YELLOW, PANEL_WIDTH // 2, 25, center=True, letter_spacing=1)
    
    # YES/NO options - SIDE BY SIDE positioning
    yes_color = GREEN if game_state['half_court_selection'] == 0 else WHITE
    no_color = RED if game_state['half_court_selection'] == 1 else WHITE
    
    # Position YES on left side, NO on right side
    draw_text_enhanced(4, "YES", yes_color, 15, 40, center=False, letter_spacing=1)
    draw_text_enhanced(4, "NO", no_color, 40, 40, center=False, letter_spacing=1)
    
    # Selection indicator arrows
    if game_state['half_court_selection'] == 0:
        draw_text_enhanced(4, ">", GREEN, 8, 40, center=False, letter_spacing=1)
    else:
        draw_text_enhanced(4, ">", RED, 33, 40, center=False, letter_spacing=1)
    
    # Simple instruction at bottom
    draw_text_enhanced(4, "ARROWS", WHITE, PANEL_WIDTH // 2, 55, center=True, letter_spacing=0)
    
    panel_buffers[4].dirty = True
    update_display()

def half_court_start_animation():
    """Optimized half court start animation with clear text"""
    for frame in range(90):
        clear_panel(4)
        
        pulse = (math.sin(frame * 0.3) + 1) / 2
        brightness = int(150 + (105 * pulse))
        color = (brightness, brightness, 0)
        
        # Clear, readable text layout
        draw_text_enhanced(4, "HALF", color, PANEL_WIDTH // 2, 12, center=True, letter_spacing=1)
        draw_text_enhanced(4, "COURT", color, PANEL_WIDTH // 2, 22, center=True, letter_spacing=1)
        draw_text_enhanced(4, "MODE", color, PANEL_WIDTH // 2, 35, center=True, letter_spacing=1)
        draw_text_enhanced(4, "START", color, PANEL_WIDTH // 2, 48, center=True, letter_spacing=1)
        
        panel_buffers[4].dirty = True
        update_display()
        time.sleep(0.033)
    
    time.sleep(1)

def draw_text_enhanced(panel_num, text, color, x, y, center=False, scale=1, letter_spacing=1):
    """Enhanced text drawing with proper spacing - FIXED for 7-letter words"""
    buffer = panel_buffers[panel_num].back_buffer
    
    # Calculate text width with reduced letter spacing to fit within panel
    text_width = len(text) * (8 + letter_spacing) * scale - letter_spacing * scale
    
    # If text is too wide, reduce letter spacing further
    if text_width > PANEL_WIDTH:
        letter_spacing = max(0, (PANEL_WIDTH - len(text) * 8 * scale) // max(1, len(text) - 1))
        text_width = len(text) * (8 + letter_spacing) * scale - letter_spacing * scale
    
    if center:
        x = x - (text_width // 2)
    
    current_x = x
    for char in text:
        if char == ' ':
            current_x += 6 * scale  # Space width
            continue
            
        pattern = get_letter_pattern(char.upper())
        if not pattern:
            current_x += (8 + letter_spacing) * scale
            continue
        
        for row_idx, row in enumerate(pattern):
            for col_idx, pixel in enumerate(row):
                if pixel == '1':
                    for sy in range(scale):
                        for sx in range(scale):
                            px = current_x + col_idx * scale + sx
                            py = y + row_idx * scale + sy
                            if 0 <= px < PANEL_WIDTH and 0 <= py < PANEL_HEIGHT:
                                buffer[py][px] = color
        
        current_x += (8 + letter_spacing) * scale
    
    panel_buffers[panel_num].dirty = True


def draw_animation_enhanced():
    """Enhanced draw animation"""
    clear_panel(4)
    draw_multiline_text_enhanced(4, "DRAW", YELLOW, line_spacing=3)
    update_display()
    time.sleep(1)
    
    clear_panel(4)
    draw_enhanced_sad_face(4)
    update_display()
    time.sleep(2)

def determine_trick_winner(trick_cards, trump_suit, lead_suit):
    """
    FIXED: Determine trick winner using the LOCKED lead suit
    """
    if not trick_cards or all(card is None for card in trick_cards):
        return None
    
    highest_trump_player = None
    highest_trump_value = -1
    highest_lead_player = None
    highest_lead_value = -1
    
    print(f"Determining winner - Trump: {trump_suit}, LOCKED Lead suit: {lead_suit}")
    
    for player, card in enumerate(trick_cards):
        if card is None:
            continue
            
        suit, rank = card
        value = RANK_VALUES[rank]
        
        print(f"  Player {player + 1}: {rank} of {suit} (value: {value})")
        
        # Check for trump cards FIRST (highest priority)
        if suit == trump_suit:
            if value > highest_trump_value:
                highest_trump_value = value
                highest_trump_player = player
                print(f"    → New highest trump: Player {player + 1}")
        
        # Check for lead suit cards (from LOCKED lead suit only)
        elif suit == lead_suit:
            if value > highest_lead_value:
                highest_lead_value = value
                highest_lead_player = player
                print(f"    → New highest lead suit: Player {player + 1}")
    
    # RULE: Trump beats everything
    if highest_trump_player is not None:
        winner = highest_trump_player
        print(f"WINNER: Player {winner + 1} with trump {trick_cards[winner][1]} of {trick_cards[winner][0]}")
        return winner
    
    # RULE: No trumps, highest card of LOCKED LEAD SUIT wins
    elif highest_lead_player is not None:
        winner = highest_lead_player
        print(f"WINNER: Player {winner + 1} with {trick_cards[winner][1]} of {trick_cards[winner][0]} (highest lead suit)")
        return winner
    
    print("ERROR: No valid winner found!")
    return None

def get_team_for_player(player):
    """Get team for player"""
    if player in TEAMS['A']:
        return 'A'
    else:
        return 'B'

def can_play_card(card, hand, current_trick, active_players):
    """
    FIXED: Always check against the FIRST played card's suit only
    """
    if card not in hand:
        return False, "Card not in hand"
    
    card_suit, card_rank = card
    
    # Get the LOCKED lead suit (from first card played)
    lead_suit = game_state.get('trick_lead_suit', None)
    
    # First card of trick - can play anything AND LOCK the lead suit
    if lead_suit is None:
        return True, f"Leading the trick - will LOCK lead suit as {card_suit}"
    
    # If playing same suit as the LOCKED lead suit - always allowed
    if card_suit == lead_suit:
        return True, f"Following LOCKED lead suit ({lead_suit})"
    
    # Playing different suit - check if player has ANY cards of the LOCKED lead suit
    has_lead_suit = any(c[0] == lead_suit for c in hand if c != card)
    
    if has_lead_suit:
        return False, f"Must follow LOCKED lead suit ({lead_suit}) - you have {lead_suit} cards!"
    else:
        return True, f"No {lead_suit} cards - can play any suit"

def get_lead_suit_and_player(current_trick, active_players):
    """
    FIXED: Get the FIRST PLAYED card's suit as the PERMANENT lead suit
    """
    # Find the FIRST player who played a card (chronologically)
    for player in active_players:
        if current_trick[player] is not None:
            lead_suit = current_trick[player][0]  # First card's suit
            print(f"LOCKED LEAD SUIT: {lead_suit} (set by Player {player + 1} - FIRST CARD)")
            return lead_suit, player
    
    return None, None  # No cards played yet

def debug_follow_suit_status(player, hand, current_trick, active_players):
    """
    FIXED: Debug helper to show follow suit status against ORIGINAL lead suit
    """
    lead_suit, lead_player = get_lead_suit_and_player(current_trick, active_players)
    
    if lead_suit:
        player_lead_cards = [c for c in hand if c[0] == lead_suit]
        print(f"DEBUG Player {player + 1}:")
        print(f"  ORIGINAL lead suit: {lead_suit} (established by Player {lead_player + 1})")
        print(f"  Player has {len(player_lead_cards)} {lead_suit} cards: {player_lead_cards}")
        print(f"  Can play other suits: {len(player_lead_cards) == 0}")
        
        # Show what cards are currently in the trick
        cards_played = []
        for p in active_players:
            if current_trick[p] is not None:
                cards_played.append(f"P{p+1}:{current_trick[p][1]} of {current_trick[p][0]}")
        print(f"  Cards in trick: {', '.join(cards_played)}")
    else:
        print(f"DEBUG Player {player + 1}: Leading the trick - can play any card")

def show_follow_suit_error_enhanced(reason):
    """
    FIXED: Enhanced follow suit error showing the ORIGINAL lead suit requirement
    """
    for frame in range(90):  # 3 seconds
        clear_panel(4)
        
        # Flashing red background
        flash = (frame // 10) % 2
        if flash:
            for y in range(PANEL_HEIGHT):
                for x in range(PANEL_WIDTH):
                    panel_buffers[4].back_buffer[y][x] = (40, 0, 0)
        
        # Error text
        error_color = WHITE if flash else RED
        
        draw_text_enhanced_fixed(4, "INVALID", error_color, PANEL_WIDTH // 2, 8, center=True)
        draw_text_enhanced_fixed(4, "PLAY!", error_color, PANEL_WIDTH // 2, 18, center=True)
        
        # Show that they must follow ORIGINAL lead suit (not any other suit)
        draw_text_enhanced_fixed(4, "FOLLOW", WHITE, PANEL_WIDTH // 2, 35, center=True)
        draw_text_enhanced_fixed(4, "LEAD", WHITE, PANEL_WIDTH // 2, 45, center=True)
        draw_text_enhanced_fixed(4, "SUIT!", WHITE, PANEL_WIDTH // 2, 55, center=True)
        
        panel_buffers[4].dirty = True
        commit_buffers()
        time.sleep(0.033)
    
    time.sleep(1)

def log_trick_progress(current_trick, active_players, trump_suit):
    """
    FIXED: Log the current state of the trick with ORIGINAL lead suit tracking
    """
    lead_suit, lead_player = get_lead_suit_and_player(current_trick, active_players)
    
    print("=== TRICK STATUS ===")
    if lead_suit:
        print(f"ORIGINAL Lead Suit: {lead_suit} (set by Player {lead_player + 1})")
    else:
        print("No lead suit yet - waiting for first card")
    
    print(f"Trump Suit: {trump_suit}")
    print("Cards played:")
    
    for player in active_players:
        if current_trick[player] is not None:
            card = current_trick[player]
            status = ""
            if card[0] == trump_suit:
                status = " (TRUMP)"
            elif lead_suit and card[0] == lead_suit:
                status = " (LEAD SUIT)"
            elif lead_suit:
                status = " (OFF-SUIT)"
            
            print(f"  Player {player + 1}: {card[1]} of {card[0]}{status}")
        else:
            print(f"  Player {player + 1}: (not played yet)")
    
    print("==================")

def show_follow_suit_error():
    """Display visual feedback for follow suit violation"""
    clear_panel(4)
    draw_text_enhanced_fixed(4, "MUST", RED, PANEL_WIDTH // 2, 10, center=True)
    draw_text_enhanced_fixed(4, "FOLLOW", RED, PANEL_WIDTH // 2, 20, center=True)
    draw_text_enhanced_fixed(4, "SUIT!", RED, PANEL_WIDTH // 2, 30, center=True)
    
    # Add blinking effect
    for _ in range(3):
        panel_buffers[4].dirty = True
        commit_buffers()
        time.sleep(0.3)
        clear_panel(4)
        commit_buffers()
        time.sleep(0.3)
    
    # Show rule reminder
    clear_panel(4)
    draw_text_enhanced_fixed(4, "Must play", WHITE, PANEL_WIDTH // 2, 8, center=True)
    draw_text_enhanced_fixed(4, "same suit", WHITE, PANEL_WIDTH // 2, 18, center=True)
    draw_text_enhanced_fixed(4, "if you have", WHITE, PANEL_WIDTH // 2, 28, center=True)
    draw_text_enhanced_fixed(4, "one!", WHITE, PANEL_WIDTH // 2, 38, center=True)
    panel_buffers[4].dirty = True
    commit_buffers()
    time.sleep(2)

def is_data():
    """Check if there is data waiting on stdin"""
    return select.select([sys.stdin], [], [], 0) == ([sys.stdin], [], [])

def get_key():
    """Get a key press"""
    if is_data():
        c = sys.stdin.read(1)
        return c
    return None

def display_completed_trick(trick_cards, trump_suit, duration=3):
    """Display completed trick for specified duration"""
    print(f"Completed trick - showing for {duration} seconds...")
    
    # Update main panel
    display_main_panel(trick_cards, trump_suit)
    
    # Keep display active for specified duration
    start_time = time.time()
    while time.time() - start_time < duration:
        # Maintain display updates
        update_display()
        time.sleep(0.1)
    
    print("Trick display completed.")

# Updated for Omi - Calculate tokens based on Omi rules
def calculate_tokens_won(tricks_won, trump_team, total_tricks=8):
    """Calculate tokens won based on Omi rules"""
    trump_team_tricks = tricks_won[trump_team]
    non_trump_team = 'B' if trump_team == 'A' else 'A'
    non_trump_team_tricks = tricks_won[non_trump_team]
    
    # Kapothi (all 8 tricks) = 3 tokens
    if trump_team_tricks == 8:
        return {trump_team: 3, non_trump_team: 0}
    elif non_trump_team_tricks == 8:
        return {trump_team: 0, non_trump_team: 3}
    
    # Trump team wins 5, 6, or 7 tricks = 1 token
    elif trump_team_tricks >= 5:
        return {trump_team: 1, non_trump_team: 0}
    
    # Non-trump team wins 5, 6, or 7 tricks = 2 tokens
    elif non_trump_team_tricks >= 5:
        return {trump_team: 0, non_trump_team: 2}
    
    # 4-4 tie = no tokens, but add pending token for next round
    else:
        return {trump_team: 0, non_trump_team: 0}

def announce_kapothi_phase():
    """Handle Kapothi announcement before 7th trick"""
    clear_panel(4)
    draw_text_enhanced(4, "ANNOUNCE", WHITE, PANEL_WIDTH // 2, 20, center=True, letter_spacing=1)
    draw_text_enhanced(4, "KAPOTHI?", YELLOW, PANEL_WIDTH // 2, 30, center=True, letter_spacing=1)
    draw_text_enhanced(4, "Y/N", GREEN, PANEL_WIDTH // 2, 45, center=True, letter_spacing=1)
    update_display()

def handle_full_court_decision(self, key, player):
    """Handle initial full court decision"""
    if key in ['p', 'P']:
        self.awaiting_full_court_decision = True
        self.full_court_player = player
        self.full_court_team = 'A' if player in [0, 2] else 'B'
        self.full_court_confirmation = True
        self.game_phase = "full_court_confirmation"
    elif key in ['o', 'O']:
        # Continue normal game
        pass

def handle_full_court_confirmation(self, key):
    """Handle full court confirmation (YES/NO)"""
    if key == '1':  # YES
        self.full_court_mode = True
        self.full_court_confirmation = False
        self.awaiting_full_court_decision = False
        self.full_court_tricks_won = 0
        # Display full court mode message
        self.show_message("FULL COURT MODE!", 2)
    elif key == '2':  # NO
        self.full_court_confirmation = False
        self.awaiting_full_court_decision = False
        self.full_court_player = None
        self.full_court_team = None

def display_full_court_confirmation_fixed(player_name):
    """FIXED: Full Court confirmation - NO L/R text, NO cutoff"""
    clear_panel(4)
    
    # Player identification - top
    draw_text_enhanced_fixed(4, f"P{player_name + 1}", WHITE, PANEL_WIDTH // 2, 5, center=True)
    
    # Question text
    draw_text_enhanced_fixed(4, "FULL", YELLOW, PANEL_WIDTH // 2, 15, center=True)
    draw_text_enhanced_fixed(4, "COURT?", YELLOW, PANEL_WIDTH // 2, 25, center=True)
    
    # YES/NO with proper spacing - NO moved further left to prevent cutoff
    yes_color = GREEN if game_state['full_court_selection'] == 0 else WHITE
    no_color = RED if game_state['full_court_selection'] == 1 else WHITE
    
    # YES at position 10, NO at position 40 (safer position)
    draw_text_enhanced_fixed(4, "YES", yes_color, 10, 40, center=False)   # Left side
    draw_text_enhanced_fixed(4, "NO", no_color, 40, 40, center=False)     # Right side (safer)
    
    # Arrow indicators
    if game_state['full_court_selection'] == 0:
        draw_text_enhanced_fixed(4, ">", GREEN, 4, 40, center=False)      # Point to YES
    else:
        draw_text_enhanced_fixed(4, ">", RED, 34, 40, center=False)       # Point to NO
    
    panel_buffers[4].dirty = True
    update_display()

def is_trump_team_player(self, player):
    """Check if player is on trump team"""
    trump_player = self.trump_player
    if trump_player in [0, 2]:  # Team A
        return player in [0, 2]
    else:  # Team B
        return player in [1, 3]
    
def full_court_start_animation_fixed():
    """Full Court start animation - EXACTLY like half_court_start_animation_fixed"""
    for frame in range(90):
        clear_panel(4)
        
        pulse = (math.sin(frame * 0.3) + 1) / 2
        brightness = int(150 + (105 * pulse))
        color = (brightness, brightness, 0)
        
        # Properly sized text for 64x64 panel - same pattern as Half Court
        draw_text_enhanced_fixed(4, "FULL", color, PANEL_WIDTH // 2, 15, center=True)
        draw_text_enhanced_fixed(4, "COURT", color, PANEL_WIDTH // 2, 25, center=True)
        draw_text_enhanced_fixed(4, "MODE", color, PANEL_WIDTH // 2, 40, center=True)
        
        panel_buffers[4].dirty = True
        update_display()
        time.sleep(0.033)
    
    time.sleep(1)

def full_court_defeat_animation_fixed(full_court_team):
    """Full Court defeat animation - EXACTLY like half_court_winner_animation"""
    opposing_team = 'A' if full_court_team == 'B' else 'B'
    
    # Use the same pattern as half_court_winner_animation(None, trump_team, False)
    
    # Clear all panels
    clear_all_panels()
    
    # Step 1: Show defeating team
    clear_panel(4)
    draw_text_enhanced_fixed(4, "TEAM", RED, PANEL_WIDTH // 2, 10, center=True)
    draw_text_enhanced_fixed(4, opposing_team, RED, PANEL_WIDTH // 2, 25, center=True)
    panel_buffers[4].dirty = True
    commit_buffers()
    time.sleep(1.0)
    
    # Step 2: Show "DEFEATS"
    clear_panel(4)
    draw_text_enhanced_fixed(4, "TEAM", RED, PANEL_WIDTH // 2, 5, center=True)
    draw_text_enhanced_fixed(4, opposing_team, RED, PANEL_WIDTH // 2, 15, center=True)
    draw_text_enhanced_fixed(4, "DEFEATS", RED, PANEL_WIDTH // 2, 30, center=True)
    panel_buffers[4].dirty = True
    commit_buffers()
    time.sleep(1.0)
    
    # Step 3: Show "FULL COURT"
    clear_panel(4)
    draw_text_enhanced_fixed(4, "TEAM", RED, PANEL_WIDTH // 2, 2, center=True)
    draw_text_enhanced_fixed(4, opposing_team, RED, PANEL_WIDTH // 2, 12, center=True)
    draw_text_enhanced_fixed(4, "DEFEATS", RED, PANEL_WIDTH // 2, 22, center=True)
    draw_text_enhanced_fixed(4, "FULL", RED, PANEL_WIDTH // 2, 32, center=True)
    draw_text_enhanced_fixed(4, "COURT!", RED, PANEL_WIDTH // 2, 42, center=True)
    panel_buffers[4].dirty = True
    commit_buffers()
    time.sleep(1.5)
    
    # Step 4: Flash effect (like Half Court)
    for i in range(4):
        clear_panel(4)
        if i % 2 == 0:
            draw_text_enhanced_fixed(4, "FULL COURT", RED, PANEL_WIDTH // 2, 15, center=True)
            draw_text_enhanced_fixed(4, "DEFEATED!", RED, PANEL_WIDTH // 2, 35, center=True)
        panel_buffers[4].dirty = True
        commit_buffers()
        time.sleep(0.4)
    
    # Final display with tokens
    clear_panel(4)
    draw_text_enhanced_fixed(4, "FULL COURT", RED, PANEL_WIDTH // 2, 10, center=True)
    draw_text_enhanced_fixed(4, "DEFEATED!", RED, PANEL_WIDTH // 2, 25, center=True)
    draw_text_enhanced_fixed(4, "-3 TOKENS", YELLOW, PANEL_WIDTH // 2, 45, center=True)
    panel_buffers[4].dirty = True
    commit_buffers()
    time.sleep(2.0)

def full_court_winner_animation(winner_info, winning_team, is_full_court_win):
    """FIXED: Full Court winner animation with CLEAR defeated team display"""
    if is_full_court_win:
        # Full court player wins all 8 tricks
        text = f"FULL COURT PLAYER {winner_info + 1} WINS!"
        color = YELLOW
        defeated_team = 'B' if game_state['full_court_team'] == 'A' else 'A'  # Opposing team defeated
        print(f"Full court player {winner_info + 1} wins all 8 tricks!")
        print(f"DEFEATED TEAM: {defeated_team} must scan cards")
    else:
        # Trump team defeats full court player
        full_court_team = game_state['full_court_team']
        defeated_team = full_court_team  # Full court team is defeated
        text = f"TEAM {winning_team} DEFEATS TEAM {defeated_team}!"
        color = GREEN if winning_team == 'A' else BLUE
        print(f"Trump Team {winning_team} defeats full court!")
        print(f"DEFEATED TEAM: {defeated_team} must scan cards")
    
    # Clear all panels first
    clear_all_panels()
    
    # Step 1: Show winning team
    clear_panel(4)
    if is_full_court_win:
        draw_text_enhanced_fixed(4, "FULL COURT", color, PANEL_WIDTH // 2, 2, center=True)
        draw_text_enhanced_fixed(4, "PLAYER", color, PANEL_WIDTH // 2, 12, center=True)
        draw_text_enhanced_fixed(4, f"{winner_info + 1}", color, PANEL_WIDTH // 2, 22, center=True)
        draw_text_enhanced_fixed(4, "WINS ALL", color, PANEL_WIDTH // 2, 32, center=True)
        draw_text_enhanced_fixed(4, "8 TRICKS!", color, PANEL_WIDTH // 2, 42, center=True)
        draw_text_enhanced_fixed(4, f"TEAM {defeated_team}", RED, PANEL_WIDTH // 2, 55, center=True)
    else:
        draw_text_enhanced_fixed(4, f"TEAM {winning_team}", color, PANEL_WIDTH // 2, 10, center=True)
        draw_text_enhanced_fixed(4, "DEFEATS", color, PANEL_WIDTH // 2, 25, center=True)
        draw_text_enhanced_fixed(4, f"TEAM {defeated_team}!", RED, PANEL_WIDTH // 2, 40, center=True)
    panel_buffers[4].dirty = True
    commit_buffers()
    time.sleep(2.0)
    
    # Step 2: Show defeated team must scan
    clear_panel(4)
    draw_text_enhanced_fixed(4, f"DEFEATED", RED, PANEL_WIDTH // 2, 10, center=True)
    draw_text_enhanced_fixed(4, f"TEAM {defeated_team}", RED, PANEL_WIDTH // 2, 20, center=True)
    draw_text_enhanced_fixed(4, "MUST SCAN", YELLOW, PANEL_WIDTH // 2, 35, center=True)
    draw_text_enhanced_fixed(4, "3 CARDS", YELLOW, PANEL_WIDTH // 2, 45, center=True)
    panel_buffers[4].dirty = True
    commit_buffers()
    time.sleep(2.0)
    
    # Continue with spectacular animation showing defeated team...
    for frame in range(120):
        clear_panel(4)
        
        # Multiple expanding circles
        center_x, center_y = PANEL_WIDTH // 2, PANEL_HEIGHT // 2
        for explosion in range(4):
            radius = (frame + explosion * 15) % 35
            if radius < 30:
                for angle in range(0, 360, 12):
                    x = center_x + int(radius * math.cos(math.radians(angle)))
                    y = center_y + int(radius * math.sin(math.radians(angle)))
                    if 0 <= x < PANEL_WIDTH and 0 <= y < PANEL_HEIGHT:
                        alpha = 1 - (radius / 30)
                        display_color = (
                            int(color[0] * alpha), 
                            int(color[1] * alpha), 
                            int(color[2] * alpha)
                        )
                        panel_buffers[4].back_buffer[y][x] = display_color
        
        # Sparkles
        for _ in range(10):
            x = random.randint(0, PANEL_WIDTH - 1)
            y = random.randint(0, PANEL_HEIGHT - 1)
            if random.random() > 0.6:
                panel_buffers[4].back_buffer[y][x] = WHITE
        
        # Show defeated team clearly
        draw_text_enhanced_fixed(4, f"TEAM {defeated_team}", RED, PANEL_WIDTH // 2, 15, center=True)
        draw_text_enhanced_fixed(4, "SCANS", YELLOW, PANEL_WIDTH // 2, 30, center=True)
        draw_text_enhanced_fixed(4, "3 CARDS", YELLOW, PANEL_WIDTH // 2, 45, center=True)
        
        panel_buffers[4].dirty = True
        update_display()
        time.sleep(0.033)
    
    time.sleep(2)

def complete_reset_after_half_court_anticlockwise():
    """Reset game state for new round with NEW ROUND animation and return new active player"""
    print("=== COMPLETE RESET AFTER DRAW/HALF COURT ===")
    
    # **NEW: Show "NEW ROUND BEGINS" animation for draw scenarios**
    print("Starting new round animation after draw...")
    new_round_animation_enhanced()
    
    # CRITICAL FIX: Anti-clockwise dealer rotation
    game_state['dealer'] = (game_state.get('dealer', 0) - 1) % 4  # Changed from +3 to -1
    game_state['trump_selector'] = (game_state['dealer'] - 1) % 4  # Anti-clockwise from dealer
    
    # Reset ALL game state variables
    game_state['phase'] = 'trump_selection'
    game_state['display_mode'] = 'normal'
    game_state['trump_suit'] = None
    game_state['trump_team'] = None
    game_state['current_trick'] = [None, None, None, None]
    game_state['trick_leader'] = None
    game_state['tricks_won'] = {'A': 0, 'B': 0}
    
    # Reset half court state completely
    game_state['half_court_mode'] = False
    game_state['half_court_player'] = None
    game_state['half_court_team'] = None
    game_state['active_players'] = [0, 1, 2, 3]
    game_state['first_four_cards_dealt'] = False
    game_state['first_four_display'] = []
    game_state['half_court_timer'] = 0
    
    # Reset full court state completely
    game_state['full_court_mode'] = False
    game_state['full_court_player'] = None
    game_state['full_court_team'] = None
    game_state['full_court_confirmation'] = False
    game_state['full_court_selection'] = 0
    game_state['full_court_tricks_won'] = 0
    game_state['first_card_played'] = False
    game_state['game_started'] = False
    game_state['any_player_can_select_full_court'] = True
    
    # Reset other game variables
    game_state['cancel_trump_mode'] = False
    game_state['cancel_trump_selection'] = 0
    game_state['last_trick_cards'] = []
    game_state['showing_last_trick'] = False
    game_state['first_trick_started'] = False
    
    # Clear panel states
    for i in range(4):
        game_state[f'panel_{i}_cleared'] = False
    
    # Increment round number
    game_state['current_round'] = game_state.get('current_round', 1) + 1
    
    print(f"New match {game_state['current_round']} starting")
    print(f"New dealer: Player {game_state['dealer'] + 1}")
    print(f"New trump selector: Player {game_state['trump_selector'] + 1}")
    
    return game_state['trump_selector']

def draw_bordered_box(buffer, start_x, start_y, width, height, border_color=WHITE):
    """Draw a bordered box on the buffer"""
    # Top and bottom borders
    for x in range(start_x, start_x + width):
        if 0 <= x < PANEL_WIDTH:
            if 0 <= start_y < PANEL_HEIGHT:
                buffer[start_y][x] = border_color
            if 0 <= start_y + height - 1 < PANEL_HEIGHT:
                buffer[start_y + height - 1][x] = border_color
    
    # Left and right borders
    for y in range(start_y, start_y + height):
        if 0 <= y < PANEL_HEIGHT:
            if 0 <= start_x < PANEL_WIDTH:
                buffer[y][start_x] = border_color
            if 0 <= start_x + width - 1 < PANEL_WIDTH:
                buffer[y][start_x + width - 1] = border_color

def draw_card_in_box(buffer, box_x, box_y, box_width, box_height, player_num, suit, rank):
    """Draw a card properly formatted within a specific box with margins"""
    # Define margins (2 pixels on each side)
    margin = 2
    content_width = box_width - (2 * margin)
    content_height = box_height - (2 * margin)
    content_x = box_x + margin
    content_y = box_y + margin
    
    # Player text at top (e.g., "P1")
    player_text = f"P{player_num + 1}"
    player_y = content_y + 2
    
    # Center the player text horizontally in the content area
    text_width = len(player_text) * 4  # Assuming 4 pixels per character
    player_x = content_x + (content_width - text_width) // 2
    
    # Draw player text
    draw_text_small(buffer, player_x, player_y, player_text, WHITE)
    
    # Suit symbol position (centered, below player text)
    suit_y = player_y + 8  # 8 pixels below player text
    suit_x = content_x + (content_width - 6) // 2  # Center 6x6 suit symbol
    
    # Draw suit symbol
    if suit == 'hearts':
        draw_heart(buffer, suit_x, suit_y, RED)
    elif suit == 'diamonds':
        draw_diamond(buffer, suit_x, suit_y, RED)
    elif suit == 'clubs':
        draw_club(buffer, suit_x, suit_y, WHITE)
    elif suit == 'spades':
        draw_spade(buffer, suit_x, suit_y, WHITE)
    
    # Rank text position (centered, below suit)
    rank_y = suit_y + 10  # 10 pixels below suit symbol
    rank_width = len(str(rank)) * 4
    rank_x = content_x + (content_width - rank_width) // 2
    
    # Draw rank
    draw_text_small(buffer, rank_x, rank_y, str(rank), WHITE)

def show_last_trick_with_proper_layout(panel_buffers, last_trick):
    """Display the last trick with proper 4-box layout and borders"""
    if not last_trick:
        return
    
    # Get the main panel buffer (assuming panel 4 is the main display)
    main_buffer = panel_buffers[4].back_buffer
    
    # Clear the main buffer
    for y in range(PANEL_HEIGHT):
        for x in range(PANEL_WIDTH):
            main_buffer[y][x] = BLACK
    
    # Define box dimensions (32x32 each with 1-pixel borders)
    box_width = 31  # 32 - 1 for border
    box_height = 31
    
    # Define positions for 4 boxes
    boxes = [
        (0, 0),           # Top-left: Player 1
        (32, 0),          # Top-right: Player 2  
        (0, 32),          # Bottom-left: Player 3
        (32, 32)          # Bottom-right: Player 4
    ]
    
    # Draw borders and cards for each box
    for i, (box_x, box_y) in enumerate(boxes):
        # Draw border around this box
        draw_bordered_box(main_buffer, box_x, box_y, box_width + 1, box_height + 1, WHITE)
        
        # Get the card info for this player from last trick
        if i < len(last_trick['cards']):
            card_info = last_trick['cards'][i]
            suit = card_info['suit']
            rank = card_info['rank']
            
            # Highlight winner's box with different border color
            if i == last_trick.get('winner', -1):
                draw_bordered_box(main_buffer, box_x, box_y, box_width + 1, box_height + 1, YELLOW)
            
            # Draw the card content within this box
            draw_card_in_box(main_buffer, box_x, box_y, box_width + 1, box_height + 1, i, suit, rank)
    
    # Mark buffer as dirty for update
    panel_buffers[4].dirty = True

def get_card_rank_value(card):
    """Get numeric value of card rank for comparison"""
    if isinstance(card, tuple):
        rank = str(card[1])
    else:
        rank = str(card[1]) if len(card) > 1 else str(card[0])
    
    rank = rank.upper()
    
    if rank == 'J':
        return 11
    elif rank == 'Q':
        return 12
    elif rank == 'K':
        return 13
    elif rank == 'A':
        return 14
    else:
        try:
            return int(rank)
        except ValueError:
            return 15

def all_cards_10_or_below(cards):
    """Check if all cards in hand are rank 10 or below - FIXED for Omi ranking"""
    for card in cards:
        rank = card[1]  # Get rank from card tuple
        # In Omi: A=14, K=13, Q=12, J=11, 10=10, 9=9, 8=8, 7=7
        # For cancel trump: only 10, 9, 8, 7 are eligible (ÃƒÆ’Ã†â€™Ãƒâ€ Ã¢â‚¬â„¢ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡Ãƒâ€šÃ‚Â¬ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â°ÃƒÆ’Ã†â€™ÃƒÂ¢Ã¢â€šÂ¬Ã…Â¡ÃƒÆ’Ã¢â‚¬Å¡Ãƒâ€šÃ‚Â¤ 10)
        if rank not in ['10', '9', '8', '7']:
            return False
    return True


def draw_text_small_bitmap(panel_num, x, y, text, color):
    """Draw text with SMALLER 3x5 pixel patterns for P-text and LARGER 6x8 for numbers"""
    # SMALLER 3x5 pixel font patterns for P1, P2, P3, P4 text
    small_char_patterns = {
        'P': [
            [1, 1, 1],
            [1, 0, 1],
            [1, 1, 1],
            [1, 0, 0],
            [1, 0, 0]
        ],
        '1': [
            [0, 1, 0],
            [1, 1, 0],
            [0, 1, 0],
            [0, 1, 0],
            [1, 1, 1]
        ],
        '2': [
            [1, 1, 1],
            [0, 0, 1],
            [1, 1, 1],
            [1, 0, 0],
            [1, 1, 1]
        ],
        '3': [
            [1, 1, 1],
            [0, 0, 1],
            [1, 1, 1],
            [0, 0, 1],
            [1, 1, 1]
        ],
        '4': [
            [1, 0, 1],
            [1, 0, 1],
            [1, 1, 1],
            [0, 0, 1],
            [0, 0, 1]
        ]
    }
    
    # LARGER 6x8 pixel font patterns for card numbers/ranks
    large_char_patterns = {
        'A': [
            [0, 1, 1, 1, 1, 0],
            [1, 1, 0, 0, 1, 1],
            [1, 1, 0, 0, 1, 1],
            [1, 1, 1, 1, 1, 1],
            [1, 1, 1, 1, 1, 1],
            [1, 1, 0, 0, 1, 1],
            [1, 1, 0, 0, 1, 1],
            [1, 1, 0, 0, 1, 1]
        ],
        'K': [
            [1, 1, 0, 0, 1, 1],
            [1, 1, 0, 1, 1, 0],
            [1, 1, 1, 1, 0, 0],
            [1, 1, 1, 0, 0, 0],
            [1, 1, 1, 1, 0, 0],
            [1, 1, 0, 1, 1, 0],
            [1, 1, 0, 0, 1, 1],
            [1, 1, 0, 0, 1, 1]
        ],
        'Q': [
            [0, 1, 1, 1, 1, 0],
            [1, 1, 0, 0, 1, 1],
            [1, 1, 0, 0, 1, 1],
            [1, 1, 0, 0, 1, 1],
            [1, 1, 0, 1, 1, 1],
            [1, 1, 0, 1, 1, 0],
            [0, 1, 1, 1, 1, 0],
            [0, 0, 0, 0, 1, 1]
        ],
        'J': [
            [1, 1, 1, 1, 1, 1],
            [0, 0, 0, 1, 1, 0],
            [0, 0, 0, 1, 1, 0],
            [0, 0, 0, 1, 1, 0],
            [1, 1, 0, 1, 1, 0],
            [1, 1, 0, 1, 1, 0],
            [1, 1, 0, 1, 1, 0],
            [0, 1, 1, 1, 0, 0]
        ],
        '7': [
            [1, 1, 1, 1, 1, 1],
            [1, 1, 1, 1, 1, 1],
            [0, 0, 0, 0, 1, 1],
            [0, 0, 0, 1, 1, 0],
            [0, 0, 1, 1, 0, 0],
            [0, 1, 1, 0, 0, 0],
            [0, 1, 1, 0, 0, 0],
            [0, 1, 1, 0, 0, 0]
        ],
        '8': [
            [0, 1, 1, 1, 1, 0],
            [1, 1, 0, 0, 1, 1],
            [1, 1, 0, 0, 1, 1],
            [0, 1, 1, 1, 1, 0],
            [0, 1, 1, 1, 1, 0],
            [1, 1, 0, 0, 1, 1],
            [1, 1, 0, 0, 1, 1],
            [0, 1, 1, 1, 1, 0]
        ],
        '9': [
            [0, 1, 1, 1, 1, 0],
            [1, 1, 0, 0, 1, 1],
            [1, 1, 0, 0, 1, 1],
            [1, 1, 0, 0, 1, 1],
            [0, 1, 1, 1, 1, 1],
            [0, 0, 0, 0, 1, 1],
            [1, 1, 0, 0, 1, 1],
            [0, 1, 1, 1, 1, 0]
        ],
        '0': [
            [0, 1, 1, 1, 1, 0],
            [1, 1, 0, 0, 1, 1],
            [1, 1, 0, 1, 1, 1],
            [1, 1, 1, 0, 1, 1],
            [1, 1, 1, 0, 1, 1],
            [1, 1, 1, 0, 1, 1],
            [1, 1, 0, 0, 1, 1],
            [0, 1, 1, 1, 1, 0]
        ],
        '1': [
            [0, 0, 1, 1, 0, 0],
            [0, 1, 1, 1, 0, 0],
            [1, 1, 1, 1, 0, 0],
            [0, 0, 1, 1, 0, 0],
            [0, 0, 1, 1, 0, 0],
            [0, 0, 1, 1, 0, 0],
            [0, 0, 1, 1, 0, 0],
            [1, 1, 1, 1, 1, 1]
        ]
    }
    
    # Determine if this is player text (P1, P2, etc.) or card rank
    is_player_text = text.startswith('P') and len(text) == 2
    
    if is_player_text:
        # Use small patterns for player text with space between P and number
        for char_index, char in enumerate(text):
            if char == 'P':
                pattern = small_char_patterns.get('P')
                char_x = x
            elif char in '1234':
                pattern = small_char_patterns.get(char)
                char_x = x + 5  # 3 pixels for P + 2 pixel space = 5 pixels offset
            
            if pattern:
                for row_idx, row in enumerate(pattern):
                    if y + row_idx >= PANEL_HEIGHT:
                        break
                    for col_idx, pixel in enumerate(row):
                        pixel_x = char_x + col_idx
                        pixel_y = y + row_idx
                        
                        if (pixel and 
                            0 <= pixel_x < PANEL_WIDTH and 
                            0 <= pixel_y < PANEL_HEIGHT):
                            panel_buffers[panel_num].back_buffer[pixel_y][pixel_x] = color
    else:
        # Use large patterns for card ranks
        for char_index, char in enumerate(text):
            if char.upper() in large_char_patterns:
                pattern = large_char_patterns[char.upper()]
                char_x = x + (char_index * 7)  # 7 pixel spacing for 6-wide patterns
                
                if char_x + 6 >= PANEL_WIDTH:
                    break
                    
                for row_idx, row in enumerate(pattern):
                    if y + row_idx >= PANEL_HEIGHT:
                        break
                    for col_idx, pixel in enumerate(row):
                        pixel_x = char_x + col_idx
                        pixel_y = y + row_idx
                        
                        if (pixel and 
                            0 <= pixel_x < PANEL_WIDTH and 
                            0 <= pixel_y < PANEL_HEIGHT):
                            panel_buffers[panel_num].back_buffer[pixel_y][pixel_x] = color

def draw_suit_symbol_bitmap(panel_num, x, y, suit, color=WHITE):
    """Draw suit symbols with EXTRA LARGE 8x8 patterns and PROPER COLORS"""
    
    # EXTRA LARGE 8x8 patterns for crystal clear suit identification
    patterns = {
        'hearts': [
            [0, 1, 1, 0, 0, 1, 1, 0],
            [1, 1, 1, 1, 1, 1, 1, 1], 
            [1, 1, 1, 1, 1, 1, 1, 1],
            [1, 1, 1, 1, 1, 1, 1, 1],
            [1, 1, 1, 1, 1, 1, 1, 1],
            [0, 1, 1, 1, 1, 1, 1, 0],
            [0, 0, 1, 1, 1, 1, 0, 0],
            [0, 0, 0, 1, 1, 0, 0, 0]
        ],
        'diamonds': [
            [0, 0, 0, 1, 1, 0, 0, 0],
            [0, 0, 1, 1, 1, 1, 0, 0],
            [0, 1, 1, 1, 1, 1, 1, 0],
            [1, 1, 1, 1, 1, 1, 1, 1],
            [1, 1, 1, 1, 1, 1, 1, 1], 
            [0, 1, 1, 1, 1, 1, 1, 0],
            [0, 0, 1, 1, 1, 1, 0, 0],
            [0, 0, 0, 1, 1, 0, 0, 0]
        ],
        'clubs': [
            [0, 0, 1, 1, 1, 1, 0, 0],
            [0, 1, 1, 1, 1, 1, 1, 0],
            [1, 1, 1, 1, 1, 1, 1, 1],
            [1, 1, 1, 1, 1, 1, 1, 1],
            [0, 1, 1, 1, 1, 1, 1, 0],
            [0, 0, 1, 1, 1, 1, 0, 0],
            [0, 0, 1, 1, 1, 1, 0, 0],
            [0, 1, 1, 1, 1, 1, 1, 0]
        ],
        'spades': [
            [0, 0, 0, 1, 1, 0, 0, 0],
            [0, 0, 1, 1, 1, 1, 0, 0],
            [0, 1, 1, 1, 1, 1, 1, 0],
            [1, 1, 1, 1, 1, 1, 1, 1],
            [1, 1, 1, 1, 1, 1, 1, 1],
            [1, 1, 1, 1, 1, 1, 1, 1],
            [0, 0, 1, 1, 1, 1, 0, 0],
            [0, 1, 1, 1, 1, 1, 1, 0]
        ]
    }
    
    # Select pattern and PROPER COLOR
    if suit == 'hearts' or suit == 'diamonds':
        pattern = patterns.get(suit, patterns['hearts'])
        draw_color = RED  # RED for hearts and diamonds
    else:  # clubs or spades
        pattern = patterns.get(suit, patterns['spades']) 
        draw_color = WHITE  # WHITE for clubs and spades
    
    # Draw with STRICT bounds checking
    for row_idx, row in enumerate(pattern):
        for col_idx, pixel in enumerate(row):
            pixel_x = x + col_idx
            pixel_y = y + row_idx
            
            if (pixel and 
                0 <= pixel_x < PANEL_WIDTH and 
                0 <= pixel_y < PANEL_HEIGHT):
                panel_buffers[panel_num].back_buffer[pixel_y][pixel_x] = draw_color

def draw_animated_border(panel_num, box_x, box_y, box_width, box_height, is_winner=False, animation_cycle=0):
    """Draw animated borders with special effects for winner cards"""
    
    if is_winner:
        # WINNER ANIMATION: Pulsing golden/yellow border with sparkle effect
        pulse_intensity = int(128 + 127 * math.sin(animation_cycle * 0.3))
        winner_color = (pulse_intensity, pulse_intensity, 0)  # Golden yellow pulsing
        
        # Draw double border for winner
        # Outer border - pulsing golden
        for x in range(box_width):
            if box_x + x < PANEL_WIDTH:
                panel_buffers[panel_num].back_buffer[box_y][box_x + x] = winner_color
                panel_buffers[panel_num].back_buffer[box_y + box_height - 1][box_x + x] = winner_color
        for y in range(box_height):
            if box_y + y < PANEL_HEIGHT:
                panel_buffers[panel_num].back_buffer[box_y + y][box_x] = winner_color
                panel_buffers[panel_num].back_buffer[box_y + y][box_x + box_width - 1] = winner_color
        
        # Inner border - bright yellow
        for x in range(1, box_width - 1):
            if box_x + x < PANEL_WIDTH:
                panel_buffers[panel_num].back_buffer[box_y + 1][box_x + x] = YELLOW
                panel_buffers[panel_num].back_buffer[box_y + box_height - 2][box_x + x] = YELLOW
        for y in range(1, box_height - 1):
            if box_y + y < PANEL_HEIGHT:
                panel_buffers[panel_num].back_buffer[box_y + y][box_x + 1] = YELLOW
                panel_buffers[panel_num].back_buffer[box_y + y][box_x + box_width - 2] = YELLOW
        
        # Add sparkle effects at corners
        sparkle_positions = [
            (box_x + 2, box_y + 2),     # Top-left
            (box_x + box_width - 3, box_y + 2),     # Top-right
            (box_x + 2, box_y + box_height - 3),     # Bottom-left
            (box_x + box_width - 3, box_y + box_height - 3)  # Bottom-right
        ]
        
        sparkle_color = WHITE if (animation_cycle // 10) % 2 == 0 else YELLOW
        for spark_x, spark_y in sparkle_positions:
            if (0 <= spark_x < PANEL_WIDTH and 0 <= spark_y < PANEL_HEIGHT):
                panel_buffers[panel_num].back_buffer[spark_y][spark_x] = sparkle_color
    else:
        # Normal white border
        for x in range(box_width):
            if box_x + x < PANEL_WIDTH:
                panel_buffers[panel_num].back_buffer[box_y][box_x + x] = WHITE
                panel_buffers[panel_num].back_buffer[box_y + box_height - 1][box_x + x] = WHITE
        for y in range(box_height):
            if box_y + y < PANEL_HEIGHT:
                panel_buffers[panel_num].back_buffer[box_y + y][box_x] = WHITE
                panel_buffers[panel_num].back_buffer[box_y + y][box_x + box_width - 1] = WHITE

def main():
    """COMPLETE MAIN FUNCTION with ENHANCED perfect text rendering and spectacular animations"""
    # Initialize remote control system
    print("Initializing Enhanced Omi Card Game with PERFECT text rendering...")
    remote_scanner = MultiplexerRemote()
    
    try:
        # Initialize game variables
        hands = []
        remaining_cards = []
        selected_indices = [0, 0, 0, 0]
        
        # Input validation variables
        last_input_time = {}
        input_cooldown = 0.3  # 300ms cooldown between inputs
        
        # Initialize game state with all features including WiFi token system
        game_state.update({
            'phase': 'welcome',
            'display_mode': 'normal',
            'dealer': 0,  # Initialize dealer
            'trump_selector': 1,  # Will be set to dealer's RIGHT
            'full_court_mode': False,
            'full_court_player': None,
            'full_court_team': None,
            'full_court_confirmation': False,
            'full_court_selection': 0,
            'full_court_tricks_won': 0,
            'game_started': False,
            'first_card_played': False,
            'first_trick_started': False,  # NEW: Track first trick
            'trick_leader': None,  # NEW: Track trick leader
            'trick_lead_suit': None,  # CRITICAL: Track locked lead suit
            'any_player_can_select_full_court': True,
            'cancel_trump_mode': False,
            'cancel_trump_selection': 0,
            'trump_canceled': False,
            'last_trick_cards': [],
            'last_trick_winner': None,
            'showing_last_trick': False,
            'current_trick_backup': [],
            # WiFi Token System variables
            'wifi_manager': None,
            'esp32_ip': None,
            'scanning_active': False,
            'scan_team': None,
            'scans_required': 0,
            'scans_completed': 0,
            'show_scan_ready': False,
            'scan_ready_timer': 0,
            'show_scans_left': False,
            'scans_left_timer': 0,
            'team_tokens': {'A': 10, 'B': 10},
            'connection_status': 'disconnected',
            'scanning_just_completed': False,  # NEW: Track scanning completion
            'round_number': 1  # NEW: Track round number for animation
        })
        
        print("Enhanced Omi Card Game - SPECTACULAR EDITION")
        print("Features: Perfect text rendering, amazing animations, all original functions preserved!")
        
        # Initialize WiFi token system
        if not initialize_wifi_token_system():
            print("WARNING: WiFi Token system not available - continuing without token management")
        else:
            print("WiFi Token system initialized successfully!")
        
        # Show enhanced welcome animation with perfect text
        welcome_animation_enhanced()
        
        # Move to loading phase
        game_state['phase'] = 'loading'
        loading_phase_enhanced()
        
        # Move to lets begin phase
        game_state['phase'] = 'lets_begin'
        lets_begin_phase_enhanced()
        
        # Initialize trump selector (FIXED: dealer's RIGHT per rules)
        if 'dealer' not in game_state:
            game_state['dealer'] = 0
        game_state['trump_selector'] = (game_state['dealer'] + 1) % 4  # DEALER'S RIGHT
        
        game_state['phase'] = 'trump_selection'
        active_player = game_state['trump_selector']
        
        print(f"Player {active_player + 1} selecting trump suit (dealer's RIGHT)...")
        
        # **MAIN ENHANCED GAME LOOP WITH PERFECT TEXT AND SPECTACULAR ANIMATIONS**
        while True:
            current_time = time.time()
            
            # Handle ESP32 WiFi messages (CRITICAL - Must be first)
            handle_esp32_wifi_messages()
            
            # FIXED: Handle scanning completion and transition to trump selection
            if game_state.get('scanning_just_completed', False):
                game_state['scanning_just_completed'] = False
                if handle_scanning_completion_and_trump_selection():
                    # NEW: Show spectacular "NEW ROUND" animation before trump selection
                    new_round_animation_enhanced()
                    active_player = game_state['trump_selector']
                    hands, remaining_cards = deal_cards_with_half_court()
                    selected_indices = [0, 0, 0, 0]
                    continue
            
            # Display token animations if active (PRIORITY DISPLAY)
            if game_state['show_scan_ready']:
                display_scan_ready_animation()
                continue
            
            if game_state['show_scans_left']:
                display_scans_left_animation()
                continue
            
            # Skip normal input processing if scanning is active
            if game_state.get('scanning_active', False):
                # Only show scanning animations, no other game input
                time.sleep(0.1)
                continue
            
            # Get input from active player's remote
            button_pressed = remote_scanner.get_player_input(active_player)
            
            # Handle remote input with enhanced display
            if button_pressed:
                player_key = f"player_{active_player}"
                
                # Check cooldown
                if (player_key in last_input_time and
                    current_time - last_input_time[player_key] < input_cooldown):
                    continue
                
                last_input_time[player_key] = current_time
                print(f"Player {active_player + 1} pressed: {button_pressed}")
                
                # **ENHANCED: Special handling for UP button during trump selection (for cancel trump)**
                if (button_pressed == 'up' and
                    game_state['phase'] == 'trump_selection' and
                    hands and
                    active_player == game_state['trump_selector'] and
                    selected_indices[active_player] == 0):  # Must be at top-left card
                    
                    trump_selector_cards = hands[active_player][:4]
                    if all_cards_10_or_below_fixed(trump_selector_cards):
                        cancel_key = f"cancel_{active_player}"
                        if (cancel_key not in last_input_time or
                            current_time - last_input_time[cancel_key] > input_cooldown * 2):
                            last_input_time[cancel_key] = current_time
                            print(f"Player {active_player + 1} attempting to cancel trump selection!")
                            print(f"Trump selector cards: {trump_selector_cards}")
                            print(f"All cards ≤ 10: {all_cards_10_or_below_fixed(trump_selector_cards)}")
                            game_state['phase'] = 'cancel_trump_confirmation'
                            game_state['cancel_trump_selection'] = 0  # Default to YES
                            continue
                    else:
                        # Show enhanced warning if trying to cancel but not eligible
                        show_invalid_cancel_warning_corrected()
                        continue
                
                # Convert remote button to game action
                if button_pressed == 'up':
                    # Handle up arrow logic (normal navigation)
                    if game_state['phase'] not in ['half_court_confirmation', 'full_court_confirmation', 'cancel_trump_confirmation']:
                        current_hand_size = len(hands[active_player]) if hands else 0
                        if current_hand_size > 0:
                            current_row = selected_indices[active_player] // 4
                            if current_row > 0:
                                new_index = selected_indices[active_player] - 4
                                if new_index >= 0:
                                    selected_indices[active_player] = new_index
                
                elif button_pressed == 'down':
                    # Handle down arrow logic
                    if game_state['phase'] not in ['half_court_confirmation', 'full_court_confirmation', 'cancel_trump_confirmation']:
                        current_hand_size = len(hands[active_player]) if hands else 0
                        if current_hand_size > 0:
                            current_row = selected_indices[active_player] // 4
                            if current_row < 1:
                                new_index = selected_indices[active_player] + 4
                                if new_index < current_hand_size:
                                    selected_indices[active_player] = new_index
                
                elif button_pressed == 'right':
                    # Handle right arrow logic
                    if game_state['phase'] == 'half_court_confirmation':
                        game_state['half_court_selection'] = 1  # NO
                    elif game_state['phase'] == 'full_court_confirmation':
                        game_state['full_court_selection'] = 1  # NO
                    elif game_state['phase'] == 'cancel_trump_confirmation':
                        game_state['cancel_trump_selection'] = 1  # NO
                    else:
                        current_hand_size = len(hands[active_player]) if hands else 0
                        if current_hand_size > 0:
                            current_col = selected_indices[active_player] % 4
                            if current_col < 3:
                                new_index = selected_indices[active_player] + 1
                                if new_index < current_hand_size:
                                    selected_indices[active_player] = new_index
                
                elif button_pressed == 'left':
                    # Handle left arrow logic
                    if game_state['phase'] == 'half_court_confirmation':
                        game_state['half_court_selection'] = 0  # YES
                    elif game_state['phase'] == 'full_court_confirmation':
                        game_state['full_court_selection'] = 0  # YES
                    elif game_state['phase'] == 'cancel_trump_confirmation':
                        game_state['cancel_trump_selection'] = 0  # YES
                    else:
                        current_hand_size = len(hands[active_player]) if hands else 0
                        if current_hand_size > 0:
                            current_col = selected_indices[active_player] % 4
                            if current_col > 0:
                                new_index = selected_indices[active_player] - 1
                                if new_index >= 0:
                                    selected_indices[active_player] = new_index
                
                elif button_pressed == 'select':
                    # Handle SELECT button (equivalent to Enter/Space)
                    if game_state['phase'] == 'trump_selection':
                        if not hands:
                            hands, remaining_cards = deal_cards_with_half_court()
                        
                        if selected_indices[active_player] < len(hands[active_player]):
                            selected_card = hands[active_player][selected_indices[active_player]]
                            game_state['trump_suit'] = selected_card[0]
                            game_state['trump_team'] = get_team_for_player(active_player)
                            
                            print(f"Trump suit selected: {game_state['trump_suit']} by Team {game_state['trump_team']}")
                            
                            # Show spectacular trump announcement with perfect text
                            trump_announcement_animation_enhanced_fixed(game_state['trump_suit'])
                            
                            game_state['display_mode'] = 'first_four_cards'
                            game_state['phase'] = 'half_court_option'
                            game_state['half_court_timer'] = time.time()
                            game_state['first_four_display'] = []
                            
                            for player_num in range(4):
                                game_state['first_four_display'].append(hands[player_num][:4])
                    
                    # **ENHANCED: Cancel trump confirmation handler**
                    elif game_state['phase'] == 'cancel_trump_confirmation':
                        if game_state['cancel_trump_selection'] == 0:  # YES - Cancel trump
                            print("Trump selection canceled! Showing cards with enhanced display...")
                            trump_selector_cards = hands[active_player][:4]
                            display_canceled_cards_fixed(trump_selector_cards)
                            
                            # Deal new cards
                            hands, remaining_cards = deal_cards_with_half_court()
                            selected_indices = [0, 0, 0, 0]
                            
                            # Reset trump selection state
                            game_state['phase'] = 'trump_selection'
                            game_state['trump_suit'] = None
                            game_state['trump_team'] = None
                            game_state['cancel_trump_mode'] = False
                            
                            print(f"Player {active_player + 1} gets new cards for trump selection!")
                        else:  # NO - Continue with current trump selection
                            game_state['phase'] = 'trump_selection'
                            game_state['cancel_trump_mode'] = False
                            print("Cancel trump declined - continuing with current cards")
                    
                    elif game_state['phase'] == 'half_court_confirmation':
                        if game_state['half_court_selection'] == 0:  # YES
                            game_state['half_court_mode'] = True
                            game_state['half_court_player'] = active_player
                            game_state['half_court_team'] = get_team_for_player(active_player)
                            
                            trump_team_players = TEAMS[game_state['trump_team']]
                            game_state['active_players'] = [active_player] + trump_team_players
                            game_state['active_players'] = list(set(game_state['active_players']))
                            
                            # Show spectacular half court animation
                            half_court_start_animation_fixed()
                            
                            game_state['phase'] = 'half_court_trump_selection'
                            game_state['trump_suit'] = None
                            game_state['half_court_display_initialized'] = False
                            active_player = game_state['half_court_player']
                            
                            for player in range(4):
                                hands[player] = hands[player][:4]
                        
                        else:  # NO - Continue to normal game with all 8 cards
                            card_index = 0
                            for player in range(4):
                                for _ in range(4):
                                    if card_index < len(remaining_cards):
                                        hands[player].append(remaining_cards[card_index])
                                        card_index += 1
                            
                            game_state['phase'] = 'giving_cards'
                            giving_cards_phase_enhanced()
                            
                            game_state['phase'] = 'start'
                            start_phase_enhanced()
                            
                            game_state['game_started'] = True
                            game_state['first_card_played'] = False
                            game_state['first_trick_started'] = False
                            game_state['any_player_can_select_full_court'] = True
                            game_state['phase'] = 'playing'
                            game_state['current_trick'] = [None, None, None, None]
                            game_state['trick_lead_suit'] = None
                            
                            # RULE COMPLIANCE: Trump selector leads first trick
                            first_player = setup_first_trick()
                            active_player = first_player
                            game_state['tricks_won'] = {'A': 0, 'B': 0}
                            
                            print("==== FULL COURT AVAILABLE ====")
                            print("Non-trump players can press SELECT to select Full Court!")
                    
                    elif game_state['phase'] == 'full_court_confirmation':
                        if game_state['full_court_selection'] == 0:  # YES
                            game_state['full_court_mode'] = True
                            game_state['full_court_confirmation'] = False
                            game_state['any_player_can_select_full_court'] = False
                            
                            # Show spectacular full court animation
                            full_court_start_animation_fixed()
                            
                            game_state['phase'] = 'full_court_trump_selection'
                            game_state['trump_suit'] = None
                            game_state['full_court_tricks_won'] = 0
                            
                            print(f"Full Court Mode activated by Player {active_player + 1}!")
                        
                        else:  # NO - Continue normal game
                            game_state['phase'] = 'playing'
                            game_state['full_court_confirmation'] = False
                            game_state['full_court_player'] = None
                            game_state['full_court_team'] = None
                            game_state['trick_lead_suit'] = None
                            
                            # RULE COMPLIANCE: Ensure trump selector leads first trick
                            if not game_state.get('first_trick_started', False):
                                first_player = setup_first_trick()
                                active_player = first_player
                            else:
                                active_player = game_state['trump_selector']
                            
                            print("Full Court declined - continuing normal game")
                    
                    elif game_state['phase'] == 'half_court_trump_selection':
                        half_court_player = game_state['half_court_player']
                        if active_player == half_court_player and selected_indices[active_player] < len(hands[active_player]):
                            selected_card = hands[active_player][selected_indices[active_player]]
                            game_state['trump_suit'] = selected_card[0]
                            
                            # Show spectacular trump announcement
                            trump_announcement_animation_enhanced_fixed(game_state['trump_suit'])
                            
                            clear_all_panels()
                            for player_num in range(4):
                                if player_num in game_state['active_players']:
                                    clear_panel(player_num)
                                    for i, card in enumerate(hands[player_num]):
                                        if card is not None:
                                            pos = CARD_POSITIONS[i]
                                            draw_card(player_num, pos[0], pos[1], card, selected=False)
                                    panel_buffers[player_num].dirty = True
                                else:
                                    clear_panel(player_num)
                            commit_buffers()
                            time.sleep(2)
                            
                            game_state['phase'] = 'playing'
                            game_state['current_trick'] = [None, None, None, None]
                            game_state['trick_lead_suit'] = None
                            
                            # **FIXED: Half court player starts first, not trump selector**
                            active_player = half_court_player
                            game_state['first_trick_started'] = True
                            game_state['trick_leader'] = half_court_player
                            game_state['tricks_won'] = {'A': 0, 'B': 0}
                            
                            print(f"HALF COURT: Player {half_court_player + 1} leads first trick!")
                    
                    elif game_state['phase'] == 'full_court_trump_selection':
                        full_court_player = game_state['full_court_player']
                        if active_player == full_court_player and selected_indices[active_player] < len(hands[active_player]):
                            selected_card = hands[active_player][selected_indices[active_player]]
                            game_state['trump_suit'] = selected_card[0]
                            
                            # Show spectacular trump announcement
                            trump_announcement_animation_enhanced_fixed(game_state['trump_suit'])
                            
                            game_state['phase'] = 'playing'
                            game_state['current_trick'] = [None, None, None, None]
                            game_state['trick_lead_suit'] = None
                            
                            # **FIXED: Full court player starts first, not trump selector**
                            active_player = full_court_player
                            game_state['first_trick_started'] = True
                            game_state['trick_leader'] = full_court_player
                            game_state['tricks_won'] = {'A': 0, 'B': 0}
                            game_state['full_court_tricks_won'] = 0
                            game_state['first_card_played'] = False
                            
                            print(f"FULL COURT: Player {full_court_player + 1} leads first trick!")
                            print("Full Court gameplay begins - must win ALL 8 tricks!")
                    
                    elif game_state['phase'] == 'playing':
                        # RULE COMPLIANCE: Setup first trick if not started
                        if not game_state.get('first_trick_started', False):
                            first_player = setup_first_trick()
                            active_player = first_player
                        
                        active_players = game_state.get('active_players', [0, 1, 2, 3])
                        
                        if active_player not in active_players:
                            print("Player not active - input ignored")
                            continue
                        
                        if selected_indices[active_player] >= len(hands[active_player]):
                            print("No card selected - input ignored")
                            continue
                        
                        selected_card = hands[active_player][selected_indices[active_player]]
                        
                        # **CRITICAL FIX: LOCK LEAD SUIT ON FIRST CARD**
                        if game_state['trick_lead_suit'] is None:
                            # First card of trick - LOCK the lead suit
                            game_state['trick_lead_suit'] = selected_card[0]
                            print(f"LEAD SUIT LOCKED: {selected_card[0]} (by Player {active_player + 1})")
                        
                        # RULE COMPLIANCE: Follow suit validation with LOCKED lead suit
                        can_play, reason = can_play_card(selected_card, hands[active_player], game_state['current_trick'], active_players)
                        
                        if not can_play:
                            print(f"Invalid card play by Player {active_player + 1}: {reason}")
                            print(f"LOCKED lead suit: {game_state['trick_lead_suit']}")
                            debug_follow_suit_status(active_player, hands[active_player], game_state['current_trick'], active_players)
                            show_follow_suit_error_enhanced(reason)  # Enhanced error display
                            continue
                        
                        print(f"Player {active_player + 1} plays {selected_card[1]} of {selected_card[0]} - {reason}")
                        
                        # Valid card play - proceed
                        game_state['current_trick'][active_player] = selected_card
                        hands[active_player].pop(selected_indices[active_player])
                        
                        if not game_state.get('first_card_played', False):
                            game_state['first_card_played'] = True
                            game_state['any_player_can_select_full_court'] = False
                            print("==== FIRST CARD PLAYED ====")
                            print("Full Court no longer available this round")
                        
                        display_main_panel(game_state['current_trick'], game_state['trump_suit'], active_player)
                        commit_buffers()
                        
                        # Adjust selected index
                        if selected_indices[active_player] >= len(hands[active_player]) and len(hands[active_player]) > 0:
                            selected_indices[active_player] = len(hands[active_player]) - 1
                        elif len(hands[active_player]) == 0:
                            selected_indices[active_player] = 0
                        
                        # Check if trick is complete
                        active_cards_played = [game_state['current_trick'][p] for p in active_players if game_state['current_trick'][p] is not None]
                        
                        if len(active_cards_played) == len(active_players):
                            display_main_panel(game_state['current_trick'], game_state['trump_suit'], active_player)
                            commit_buffers()
                            time.sleep(3)
                            
                            # **ENHANCED: Store the completed trick AND winner BEFORE clearing**
                            game_state['last_trick_cards'] = game_state['current_trick'].copy()
                            
                            # RULE COMPLIANCE: Determine trick winner with LOCKED lead suit
                            locked_lead_suit = game_state['trick_lead_suit']
                            trick_cards_for_winner = [game_state['current_trick'][p] for p in active_players]
                            winner_index = determine_trick_winner(trick_cards_for_winner, game_state['trump_suit'], locked_lead_suit)
                            
                            if winner_index is not None:
                                actual_winner = active_players[winner_index]
                                
                                # **ENHANCED: Store winner information for animation**
                                game_state['last_trick_winner'] = actual_winner
                                
                                winning_team = get_team_for_player(actual_winner)
                                game_state['tricks_won'][winning_team] += 1
                                
                                print(f"Player {actual_winner + 1} (Team {winning_team}) won the trick!")
                                print(f"Tricks won - Team A: {game_state['tricks_won']['A']}, Team B: {game_state['tricks_won']['B']}")
                                
                                # Show spectacular trick winner animation
                                display_trick_winner_animation(actual_winner, winning_team, duration=3)
                                
                                # **CRITICAL: Clear lead suit for new trick**
                                game_state['trick_lead_suit'] = None
                                print("Lead suit cleared for new trick")
                                
                                # Check for Full Court mode
                                if game_state.get('full_court_mode', False):
                                    full_court_team = game_state['full_court_team']
                                    if winning_team != full_court_team:
                                        print("Full court team lost a trick - FULL COURT FAILED!")
                                        full_court_winner_animation(None, winning_team, False)
                                        
                                        # FIXED: Defeated full court team scans cards
                                        defeated_team = full_court_team  # Full court team is defeated
                                        trigger_wifi_token_scan(defeated_team, 3)
                                        
                                        if game_state['team_tokens']['A'] <= 0 or game_state['team_tokens']['B'] <= 0:
                                            winner_team = 'B' if game_state['team_tokens']['A'] <= 0 else 'A'
                                            winner_animation_enhanced(winner_team)
                                            break
                                        else:
                                            # Wait for scanning to complete before proceeding
                                            continue
                                    else:
                                        game_state['full_court_tricks_won'] += 1
                                        print(f"Full court team won trick {game_state['full_court_tricks_won']}/8")
                                        
                                        if game_state['full_court_tricks_won'] == 8:
                                            print("Full court player won all 8 tricks!")
                                            full_court_winner_animation(game_state['full_court_player'], full_court_team, True)
                                            
                                            # FIXED: Opposing team (defeated) scans cards
                                            defeated_team = 'B' if full_court_team == 'A' else 'A'
                                            trigger_wifi_token_scan(defeated_team, 3)
                                            
                                            if game_state['team_tokens']['A'] >= 10 or game_state['team_tokens']['B'] >= 10:
                                                winner_team = 'A' if game_state['team_tokens']['A'] >= 10 else 'B'
                                                winner_animation_enhanced(winner_team)
                                                break
                                            else:
                                                # Wait for scanning to complete before proceeding
                                                continue
                                        else:
                                            # **CLEAR CURRENT TRICK AFTER STORING**
                                            game_state['current_trick'] = [None, None, None, None]
                                            
                                            # RULE COMPLIANCE: Winner leads next trick
                                            game_state['trick_leader'] = actual_winner
                                            active_player = actual_winner
                                
                                # Check for half court mode
                                elif game_state.get('half_court_mode', False):
                                    half_court_team = game_state['half_court_team']
                                    trump_team = game_state['trump_team']
                                    
                                    if winning_team == trump_team:
                                        print("Half court player lost a trick - MATCH OVER!")
                                        half_court_winner_animation(None, trump_team, False)
                                        
                                        # FIXED: Defeated half court team scans cards
                                        defeated_team = half_court_team  # Half court team is defeated
                                        trigger_wifi_token_scan(defeated_team, 2)
                                        
                                        if game_state['team_tokens']['A'] <= 0 or game_state['team_tokens']['B'] <= 0:
                                            winner_team = 'B' if game_state['team_tokens']['A'] <= 0 else 'A'
                                            winner_animation_enhanced(winner_team)
                                            break
                                        else:
                                            # Wait for scanning to complete before proceeding
                                            continue
                                    
                                    elif winning_team == half_court_team:
                                        if sum(game_state['tricks_won'].values()) == 4:
                                            print("Half court player won all 4 tricks!")
                                            half_court_winner_animation(game_state['half_court_player'], half_court_team, True)
                                            
                                            # FIXED: Defeated trump team scans cards
                                            defeated_team = trump_team  # Trump team is defeated
                                            trigger_wifi_token_scan(defeated_team, 2)
                                            
                                            if game_state['team_tokens']['A'] <= 0 or game_state['team_tokens']['B'] <= 0:
                                                winner_team = 'B' if game_state['team_tokens']['A'] <= 0 else 'A'
                                                winner_animation_enhanced(winner_team)
                                                break
                                            else:
                                                # Wait for scanning to complete before proceeding
                                                continue
                                        else:
                                            # **CLEAR CURRENT TRICK AFTER STORING**
                                            game_state['current_trick'] = [None, None, None, None]
                                            
                                            # RULE COMPLIANCE: Winner leads next trick
                                            game_state['trick_leader'] = actual_winner
                                            active_player = actual_winner
                                
                                else:
                                    # Normal game completion check
                                    total_tricks = sum(game_state['tricks_won'].values())
                                    
                                    if total_tricks >= 8:
                                        print("Normal hand completed - 8 tricks played!")
                                        display_main_panel(game_state['current_trick'], game_state['trump_suit'], active_player)
                                        commit_buffers()
                                        time.sleep(2)
                                        
                                        team_a_tricks = game_state['tricks_won']['A']
                                        team_b_tricks = game_state['tricks_won']['B']
                                        
                                        if team_a_tricks > team_b_tricks:
                                            hand_winner = 'A'
                                        elif team_b_tricks > team_a_tricks:
                                            hand_winner = 'B'
                                        else:
                                            hand_winner = None
                                        
                                        if hand_winner:
                                            # **ENHANCED: Call spectacular animation with token scanning for DEFEATED team**
                                            team_won_round_animation_enhanced_wifi(hand_winner)
                                            
                                            game_state['team_scores'][hand_winner] += 1
                                            
                                            if game_state['team_scores'][hand_winner] >= 3:
                                                winner_animation_enhanced(hand_winner)
                                                break
                                            else:
                                                # Wait for scanning to complete before proceeding
                                                continue
                                        else:
                                            # NEW: Draw case - show draw animation then new round animation
                                            draw_animation_enhanced()
                                            
                                            # NEW: Show spectacular new round animation for draw case
                                            game_state['round_number'] += 1
                                            new_round_animation_enhanced()
                                            
                                            active_player = complete_reset_after_half_court_anticlockwise()
                                            hands, remaining_cards = deal_cards_with_half_court()
                                            selected_indices = [0, 0, 0, 0]
                                            continue
                                    else:
                                        # **CLEAR CURRENT TRICK AFTER STORING** - Continue to next trick
                                        game_state['current_trick'] = [None, None, None, None]
                                        
                                        # RULE COMPLIANCE: Winner leads next trick
                                        game_state['trick_leader'] = actual_winner
                                        active_player = actual_winner
                            else:
                                # RULE COMPLIANCE: Move to next player anticlockwise
                                active_player = get_next_active_player_anticlockwise(active_player, active_players)
                        else:
                            # RULE COMPLIANCE: Move to next player anticlockwise
                            active_player = get_next_active_player_anticlockwise(active_player, active_players)
            
            # Check for special remote combinations
            # Check if any non-trump player wants Half Court (during first_four_cards phase)
            if game_state.get('display_mode') == 'first_four_cards':
                non_trump_players = get_non_trump_team_players()
                for potential_player in non_trump_players:
                    button = remote_scanner.get_player_input(potential_player)
                    if button == 'select':  # Use SELECT button for Half Court option
                        player_key = f"halfcourt_{potential_player}"
                        if (player_key not in last_input_time or
                            current_time - last_input_time[player_key] > input_cooldown):
                            last_input_time[player_key] = current_time
                            game_state['phase'] = 'half_court_confirmation'
                            game_state['display_mode'] = 'normal'
                            active_player = potential_player
                            game_state['half_court_selection'] = 0
                            print(f"Player {active_player + 1} wants Half Court!")
                            break
            
            # Check for Full Court during playing phase
            elif (game_state['phase'] == 'playing' and
                  game_state.get('game_started', False) and
                  not game_state.get('first_card_played', False) and
                  not game_state.get('full_court_mode', False) and
                  not game_state.get('half_court_mode', False) and
                  not game_state.get('full_court_confirmation', False)):
                
                non_trump_players = get_non_trump_team_players()
                for potential_player in non_trump_players:
                    button = remote_scanner.get_player_input(potential_player)
                    if button == 'select':  # Use SELECT for Full Court too
                        player_key = f"fullcourt_{potential_player}"
                        if (player_key not in last_input_time or
                            current_time - last_input_time[player_key] > input_cooldown):
                            last_input_time[player_key] = current_time
                            print(f"Full Court attempt by Player {potential_player + 1}!")
                            game_state['phase'] = 'full_court_confirmation'
                            game_state['full_court_player'] = potential_player
                            game_state['full_court_team'] = get_team_for_player(potential_player)
                            game_state['full_court_confirmation'] = True
                            game_state['full_court_selection'] = 0
                            active_player = potential_player
                            break
            
            # Last trick viewing (during playing phase)
            if (game_state['phase'] == 'playing' and
                not game_state.get('showing_last_trick', False)):
                # Use DOWN button when at bottom cards to view last trick
                view_button = remote_scanner.get_player_input(active_player)
                if (view_button == 'down' and
                    selected_indices[active_player] >= len(hands[active_player]) - 4):
                    
                    last_trick = game_state.get('last_trick_cards', [])
                    last_trick_winner = game_state.get('last_trick_winner', None)
                    
                    if last_trick:
                        view_key = f"lasttrick_{active_player}"
                        if (view_key not in last_input_time or
                            current_time - last_input_time[view_key] > input_cooldown * 3):
                            last_input_time[view_key] = current_time
                            print(f"Player {active_player + 1} viewing ENHANCED last trick with perfect display...")
                            
                            game_state['showing_last_trick'] = True
                            
                            # ENHANCED: 6-second display with spectacular animation cycles
                            display_last_trick_cards_corrected(last_trick, active_player)
                            
                            game_state['showing_last_trick'] = False
            
            # **ENHANCED DISPLAY LOGIC WITH PERFECT TEXT AND SPECTACULAR EFFECTS**
            if game_state.get('display_mode') == 'first_four_cards':
                for player_num in range(4):
                    clear_panel(player_num)
                    first_four = game_state.get('first_four_display', [[], [], [], []])[player_num]
                    for card_index, card in enumerate(first_four):
                        if card is not None:
                            pos = CARD_POSITIONS[card_index]
                            draw_card(player_num, pos[0], pos[1], card, selected=False)
                    panel_buffers[player_num].dirty = True
                
                clear_panel(4)
                elapsed = time.time() - game_state.get('half_court_timer', time.time())
                remaining = max(0, 5 - int(elapsed))
                
                # Use perfect text rendering
                draw_perfect_text(4, "HALF COURT", WHITE, 5)
                draw_perfect_text(4, "OPTION", YELLOW, 15)
                draw_perfect_text(4, "PRESS", CYAN, 30)
                draw_perfect_text(4, "SELECT", CYAN, 40)
                draw_perfect_text(4, f"TIME: {remaining}", RED, 55)
                
                # Show WiFi connection status
                display_connection_status()
                panel_buffers[4].dirty = True
                
                if elapsed >= 5.0:
                    game_state['display_mode'] = 'normal'
                    card_index = 0
                    for player in range(4):
                        for _ in range(4):
                            if card_index < len(remaining_cards):
                                hands[player].append(remaining_cards[card_index])
                                card_index += 1
                    
                    game_state['phase'] = 'giving_cards'
                    giving_cards_phase_enhanced()
                    
                    game_state['phase'] = 'start'
                    start_phase_enhanced()
                    
                    game_state['game_started'] = True
                    game_state['first_card_played'] = False
                    game_state['first_trick_started'] = False
                    game_state['any_player_can_select_full_court'] = True
                    game_state['phase'] = 'playing'
                    game_state['current_trick'] = [None, None, None, None]
                    game_state['trick_lead_suit'] = None
                    
                    # RULE COMPLIANCE: Trump selector leads first trick
                    first_player = setup_first_trick()
                    active_player = first_player
                    game_state['tricks_won'] = {'A': 0, 'B': 0}
                    
                    print("==== FULL COURT AVAILABLE ====")
                
                commit_buffers()
            
            elif game_state['phase'] == 'trump_selection':
                if not hands:
                    hands, remaining_cards = deal_cards_with_half_court()
                
                display_trump_selection_phase_enhanced(hands, active_player, selected_indices[active_player])
                
                # Show WiFi connection status
                display_connection_status()
            
            elif game_state['phase'] == 'half_court_trump_selection':
                half_court_player = game_state.get('half_court_player')
                if half_court_player is not None:
                    if not game_state.get('half_court_display_initialized', False):
                        for i in range(4):
                            clear_panel(i)
                        
                        active_players = game_state.get('active_players', [])
                        for player_num in active_players:
                            if player_num != half_court_player:
                                for card_index, card in enumerate(hands[player_num]):
                                    if card is not None:
                                        pos = CARD_POSITIONS[card_index]
                                        draw_card(player_num, pos[0], pos[1], card, selected=False)
                                panel_buffers[player_num].dirty = True
                        
                        clear_panel(4)
                        draw_perfect_text(4, "HALF", WHITE, 15)
                        draw_perfect_text(4, "COURT", WHITE, 25)
                        draw_perfect_text(4, "TRUMP", YELLOW, 40)
                        
                        display_connection_status()
                        panel_buffers[4].dirty = True
                        game_state['half_court_display_initialized'] = True
                    
                    if active_player == half_court_player:
                        display_trump_selection_phase_enhanced(hands, half_court_player, selected_indices[half_court_player])
            
            elif game_state['phase'] == 'full_court_trump_selection':
                full_court_player = game_state.get('full_court_player')
                if full_court_player is not None:
                    clear_panel(4)
                    draw_perfect_text(4, "FULL", WHITE, 15)
                    draw_perfect_text(4, "COURT", WHITE, 25)
                    draw_perfect_text(4, "TRUMP", YELLOW, 40)
                    
                    display_connection_status()
                    panel_buffers[4].dirty = True
                    
                    if active_player == full_court_player:
                        display_trump_selection_phase_enhanced(hands, full_court_player, selected_indices[full_court_player])
            
            elif game_state['phase'] == 'half_court_confirmation':
                display_half_court_confirmation_fixed(active_player)
                display_connection_status()
            
            elif game_state['phase'] == 'full_court_confirmation':
                display_full_court_confirmation_fixed(active_player)
                display_connection_status()
            
            elif game_state['phase'] == 'cancel_trump_confirmation':
                display_cancel_trump_confirmation()
                display_connection_status()
                
                # Show current hands for reference
                for player in range(4):
                    if len(hands[player]) > 0:
                        selection_index = selected_indices[player] if player == active_player else -1
                        display_player_hand(player, hands[player], selection_index)
            
            elif game_state['phase'] == 'playing':
                # **CRITICAL: Skip normal display when showing last trick or scanning**
                if not game_state.get('showing_last_trick', False) and not game_state.get('scanning_active', False):
                    active_players = game_state.get('active_players', [0, 1, 2, 3])
                    
                    for i in range(4):
                        if i in active_players and len(hands[i]) > 0:
                            selection_index = selected_indices[i] if i == active_player else -1
                            display_player_hand(i, hands[i], selection_index)
                        elif i not in active_players:
                            if not game_state.get(f'panel_{i}_cleared', False):
                                clear_panel(i)
                                game_state[f'panel_{i}_cleared'] = True
                    
                    display_main_panel(game_state['current_trick'], game_state['trump_suit'], active_player)
                    
                    # **ENHANCED: Full Court availability indicator with perfect text**
                    if (game_state.get('any_player_can_select_full_court', False) and
                        not game_state.get('first_card_played', False) and
                        not game_state.get('full_court_mode', False) and
                        not game_state.get('half_court_mode', False)):
                        
                        draw_perfect_text(4, "FC AVAIL", GREEN, 2)
                        panel_buffers[4].dirty = True
                    
                    # Always show WiFi connection status during gameplay
                    display_connection_status()
            
            if game_state.get('display_mode') != 'first_four_cards':
                commit_buffers()
            
            time.sleep(0.01)  # Small delay to prevent overwhelming the GPIO
    
    except KeyboardInterrupt:
        print("\nGame interrupted by user")
    except Exception as e:
        print(f"An error occurred: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Enhanced cleanup
        print("Cleaning up...")
        
        # Close WiFi token manager
        if game_state.get('wifi_manager'):
            print("Closing WiFi token manager...")
            game_state['wifi_manager'].close()
        
        # Close remote scanner
        print("Cleaning up remote controls...")
        remote_scanner.cleanup()
        
        # Clear display
        print("Clearing display...")
        matrix.Clear()
        
        print("Enhanced game ended. All systems cleaned up properly.")

def complete_reset_after_half_court_anticlockwise():
    """Reset game state for new round and return new active player"""
    # Reset all game modes
    game_state['half_court_mode'] = False
    game_state['half_court_player'] = None
    game_state['half_court_team'] = None
    game_state['half_court_display_initialized'] = False
    
    # Reset Full Court variables
    game_state['full_court_mode'] = False
    game_state['full_court_player'] = None
    game_state['full_court_team'] = None
    game_state['full_court_confirmation'] = False
    game_state['full_court_selection'] = 0
    game_state['full_court_tricks_won'] = 0
    game_state['first_card_played'] = False
    game_state['game_started'] = False
    game_state['any_player_can_select_full_court'] = True
    
    # Reset Cancel Trump and Last Trick variables
    game_state['cancel_trump_mode'] = False
    game_state['cancel_trump_selection'] = 0
    game_state['last_trick_cards'] = []  # **CORRECTED: Reset last trick**
    game_state['showing_last_trick'] = False
    
    # Reset display and phase
    game_state['display_mode'] = 'normal'
    game_state['phase'] = 'trump_selection'
    game_state['active_players'] = [0, 1, 2, 3]
    
    # Clear panel states
    for i in range(4):
        game_state[f'panel_{i}_cleared'] = False
    
    # Move dealer anti-clockwise
    game_state['dealer'] = (game_state['dealer'] - 1) % 4
    game_state['trump_selector'] = (game_state['dealer'] - 1) % 4
    
    return game_state['trump_selector']

# Fixed text display function
def draw_text_enhanced_fixed(panel_num, text, color, x, y, center=False, scale=1, letter_spacing=1):
    """KEEPING ORIGINAL FUNCTION NAME - Enhanced text drawing with perfect spacing"""
    if center:
        draw_perfect_text(panel_num, text, color, y, center_x=x)
    else:
        draw_perfect_text(panel_num, text, color, y)

# Fixed trump announcement function
def trump_announcement_animation_enhanced_fixed(trump_suit):
    """Spectacular trump announcement with perfect text and amazing effects"""
    suit_names = {
        'hearts': 'HEARTS',
        'diamonds': 'DIAMOND', 
        'clubs': 'CLUBS',
        'spades': 'SPADES'
    }
    
    suit_name = suit_names.get(trump_suit, trump_suit.upper())
    suit_color = SUIT_COLORS[trump_suit]
    
    # Phase 1: Perfect text fade-in (2 seconds)
    for frame in range(60):
        clear_panel(4)
        
        # Calculate fade alpha
        alpha = min(1.0, frame / 30.0)
        
        # Create faded colors
        faded_white = tuple(int(WHITE[i] * alpha) for i in range(3))
        faded_suit_color = tuple(int(suit_color[i] * alpha) for i in range(3))
        
        # Draw perfect text with fade effect
        draw_perfect_text(4, "TRUMP", faded_white, 8)
        draw_perfect_text(4, suit_name, faded_suit_color, 20)
        
        panel_buffers[4].dirty = True
        commit_buffers()
        time.sleep(0.033)
    
    # Phase 2: Spectacular pulsing display with suit symbol (3 seconds)
    for frame in range(90):
        clear_panel(4)
        
        # Create background shimmer
        for y in range(PANEL_HEIGHT):
            for x in range(PANEL_WIDTH):
                shimmer = math.sin((x * 0.1 + y * 0.1 + frame * 0.2)) * 0.3 + 0.7
                if shimmer > 0.8:
                    intensity = int(30 * (shimmer - 0.8) / 0.2)
                    panel_buffers[4].back_buffer[y][x] = (intensity, intensity, intensity // 2)
        
        # Spectacular pulsing effect
        pulse = (math.sin(frame * 0.2) + 1) / 2
        pulse_brightness = int(180 + (75 * pulse))
        
        pulse_white = tuple(min(255, pulse_brightness) for _ in range(3))
        pulse_suit_color = tuple(
            min(255, int(suit_color[i] * pulse_brightness / 255)) for i in range(3)
        )
        
        # Draw pulsing text with effects
        text_effects = {'pulse': True, 'glow': True}
        draw_spectacular_text(4, "TRUMP", pulse_white, 8, text_effects)
        draw_spectacular_text(4, suit_name, pulse_suit_color, 20, text_effects)
        
        # Draw spectacular suit symbol
        if trump_suit in symbols:
            symbol_data = symbols[trump_suit]
            symbol_x = (PANEL_WIDTH - 16) // 2
            symbol_y = 35
            
            for y, row in enumerate(symbol_data[:16]):
                for x, pixel in enumerate(row[:16]):
                    if pixel == '1':
                        px = symbol_x + x
                        py = symbol_y + y
                        if 0 <= px < PANEL_WIDTH and 0 <= py < PANEL_HEIGHT:
                            # Add glow effect to symbol
                            glow_color = tuple(min(255, c + 50) for c in pulse_suit_color)
                            panel_buffers[4].back_buffer[py][px] = glow_color
                            
                            # Add sparkle effects randomly
                            if random.random() > 0.95:
                                panel_buffers[4].back_buffer[py][px] = WHITE
        
        panel_buffers[4].dirty = True
        commit_buffers()
        time.sleep(0.033)
    
    time.sleep(0.5)

# Fixed half court display functions
def display_half_court_confirmation_fixed(player_name):
    """FIXED: Half court confirmation - NO L/R text, NO cutoff"""
    clear_panel(4)
    
    # Player identification - top
    draw_text_enhanced_fixed(4, f"P{player_name + 1}", WHITE, PANEL_WIDTH // 2, 5, center=True)
    
    # Question text
    draw_text_enhanced_fixed(4, "HALF", YELLOW, PANEL_WIDTH // 2, 15, center=True)
    draw_text_enhanced_fixed(4, "COURT?", YELLOW, PANEL_WIDTH // 2, 25, center=True)
    
    # YES/NO with proper spacing - NO moved further left to prevent cutoff
    yes_color = GREEN if game_state['half_court_selection'] == 0 else WHITE
    no_color = RED if game_state['half_court_selection'] == 1 else WHITE
    
    # YES at position 10, NO at position 40 (safer position)
    draw_text_enhanced_fixed(4, "YES", yes_color, 10, 40, center=False)   # Left side
    draw_text_enhanced_fixed(4, "NO", no_color, 40, 40, center=False)     # Right side (safer)
    
    # Arrow indicators
    if game_state['half_court_selection'] == 0:
        draw_text_enhanced_fixed(4, ">", GREEN, 4, 40, center=False)      # Point to YES
    else:
        draw_text_enhanced_fixed(4, ">", RED, 34, 40, center=False)       # Point to NO
    
    panel_buffers[4].dirty = True
    update_display()
    print("Hello world")

def get_next_active_player_anticlockwise(current_player, active_players):
    """Get next player in STRICT anticlockwise order (0ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢3ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢2ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢1ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢0)"""
    # Standard anticlockwise sequence for all 4 players
    anticlockwise_order = [0, 3, 2, 1]
    
    # Filter to only include active players while maintaining order
    active_anticlockwise = [p for p in anticlockwise_order if p in active_players]
    
    if current_player not in active_anticlockwise:
        return active_anticlockwise[0]
    
    current_index = active_anticlockwise.index(current_player)
    next_index = (current_index + 1) % len(active_anticlockwise)
    
    next_player = active_anticlockwise[next_index]
    print(f"Turn order: Player {current_player + 1} ÃƒÆ’Ã†â€™Ãƒâ€šÃ‚Â¢ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬Ãƒâ€šÃ‚Â ÃƒÆ’Ã‚Â¢ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¬ÃƒÂ¢Ã¢â‚¬Å¾Ã‚Â¢ Player {next_player + 1} (anticlockwise)")
    return next_player

if __name__  == "__main__":
    main()


