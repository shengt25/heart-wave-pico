from src.state.state import State
from src.utils import load_users_list


class UserSelect(State):
    """User selection state - first screen on startup.
    Displays list of users from users.json.
    User must select one to proceed (mandatory selection).
    Selected user ID is stored in state_machine.context['user_id'].
    """

    def __init__(self, state_machine):
        super().__init__(state_machine)
        self._selection = 0
        self._page = 0
        self._user_items = []  # display items: ["ID: NAME", ...]
        self._user_ids = []  # parallel array of IDs
        self._listview_users = None

    def enter(self, args):
        # Load user data
        self._user_items.clear()
        self._user_ids.clear()

        try:
            users_dict = load_users_list()
            # Sort by ID for display
            sorted_users = sorted(users_dict.items())

            for user_id, user_name in sorted_users:
                self._user_items.append(f"{user_id}. {user_name}")
                self._user_ids.append(user_id)

            # Handle empty users list
            if len(self._user_items) == 0:
                raise OSError("No users found")

        except Exception as e:
            self._view.add_text(text="Error loading", x=0, y=0)
            self._view.add_text(text="user profiles", x=0, y=14)
            return

        # UI setup
        self._view.add_text(text="Select User", x=0, y=0, invert=True)
        self._listview_users = self._view.add_list(items=self._user_items, y=14)
        self._listview_users.set_page(self._page)
        self._listview_users.set_selection(self._selection)

        # Rotary encoder setup
        self._rotary_encoder.enable_rotate(
            items_count=len(self._user_items),
            position=self._selection
        )
        self._rotary_encoder.enable_press()

    def loop(self):
        event = self._rotary_encoder.get_event()

        if event == self._rotary_encoder.EVENT_ROTATE:
            # Update selection display
            self._listview_users.set_selection(self._rotary_encoder.get_position())

        elif event == self._rotary_encoder.EVENT_PRESS:
            # Save current selection
            self._selection = self._rotary_encoder.get_position()
            self._page = self._listview_users.get_page()

            # Get selected user ID
            selected_user_id = self._user_ids[self._selection]

            # Store in state machine context
            self._state_machine.set_context('user_id', selected_user_id)

            # Clean up and transition to main menu
            self._rotary_encoder.disable_rotate()
            self._view.remove_all()
            self._state_machine.set(state_code=self._state_machine.STATE_MENU)
