from traceback import format_exc
from tkinter import (
    Tk,
    Frame,
    Text,
    Label,
    END,
    INSERT,
    Button,
    Menu,
    Scrollbar,
    font,
    Canvas,
    TclError,
)

from lua import LuaObject, ParsingError

SYNTAX_KEYWORDS_COLOR = "#e83b99"
SYNTAX_OPERATIONS_COLOR = "#e83b99"
SYNTAX_NAMES_COLOR = "#e2e2e2"
SYNTAX_NUMBERS_COLOR = "#bd7655"
SYNTAX_STRINGS_COLOR = "#3ada76"
SYNTAX_FUNCTIONS_COLOR = "#39d3d3"
SYNTAX_COMMENTS_COLOR = "#757575"
SYNTAX_OTHER_COLOR = "#757575"

HIGHLIGHT_COLOR = "#1A354C"

APP_MAIN_BG = "#2b2b2b"

# TODO: refactor this mess


def run_app():
    """simple gui tkinter app"""

    root = Tk()
    root.title("Stormworks Lua Minifier")
    root.geometry("950x450")
    root.configure(bg=APP_MAIN_BG)

    # fonts
    text_font = font.Font(family="Consolas", size=12)
    label_font = font.Font(family="Segoe UI", size=10, weight="bold")
    button_font = font.Font(family="Segoe UI", size=10, weight="bold")
    cursor_font = font.Font(family="Segoe UI", size=9)

    # left text box
    left_frame = Frame(root, bg=APP_MAIN_BG)
    left_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
    root.columnconfigure(0, weight=1)

    line_numbers = Canvas(
        left_frame,
        width=40,
        bg=APP_MAIN_BG,
        highlightthickness=0,
    )
    line_numbers.pack(side="left", fill="y")

    left_text = Text(
        left_frame,
        bg="#1e1e1e",
        fg=SYNTAX_OTHER_COLOR,
        insertbackground="red",
        font=text_font,
        tabs=(text_font.measure("    "),),
        undo=True,
    )
    left_text.pack(side="left", fill="both", expand=True)
    left_text.tag_configure(
        "highlight",
        background=HIGHLIGHT_COLOR,
        relief="raised",
    )
    left_text.tag_lower("highlight")
    left_text.focus_set()

    # center frame
    center_frame = Frame(root, bg=APP_MAIN_BG)
    center_frame.grid(row=0, column=1, sticky="ns")
    center_frame.columnconfigure(0, weight=1)

    orig_len_label = Label(
        center_frame,
        text="Original length: 0",
        bg=APP_MAIN_BG,
        fg="white",
        font=label_font,
    )
    orig_len_label.grid(row=0, column=0, pady=(20, 2))
    rev_len_label = Label(
        center_frame,
        text="Minified length: 0",
        bg=APP_MAIN_BG,
        fg="white",
        font=label_font,
    )
    rev_len_label.grid(row=1, column=0, pady=2)
    prop_label = Label(
        center_frame,
        text="Proportion: 0.00",
        bg=APP_MAIN_BG,
        fg="white",
        font=label_font,
    )
    prop_label.grid(row=2, column=0, pady=(2, 10))
    cursor_label = Label(
        center_frame,
        text="Line: 1, Col: 1",
        bg=APP_MAIN_BG,
        fg="white",
        font=cursor_font,
    )
    cursor_label.grid(row=5, column=0, pady=(10, 0))

    # right text box
    right_text = Text(
        root,
        bg="#1a1a1a",
        fg="#aaaaaa",
        font=text_font,
        state="disabled",
        tabs=(text_font.measure("    "),),
    )
    right_text.grid(row=0, column=2, sticky="nsew", padx=10, pady=10)
    right_text.tag_configure(
        "highlight",
        background=HIGHLIGHT_COLOR,
        relief="raised",
    )
    root.columnconfigure(2, weight=1)

    # scrollbar stuff
    scrollbar = Scrollbar(left_frame)
    scrollbar.pack(side="right", fill="y")
    left_text.config(
        yscrollcommand=lambda *args: (scrollbar.set(*args), sync_scroll(*args))
    )
    scrollbar.config(
        command=lambda *args: (left_text.yview(*args), line_numbers.yview(*args))
    )

    syntax_highlight_tags = [
        "comment",
        "keyword",
        "op",
        "dot",
        "string",
        "numeral",
        "id",
        "function",
    ]

    cursive_font = font.Font(family="Consolas", size=12, slant="italic")
    left_text.tag_config("comment", font=cursive_font, foreground=SYNTAX_COMMENTS_COLOR)
    right_text.tag_config(
        "comment", font=cursive_font, foreground=SYNTAX_COMMENTS_COLOR
    )

    left_text.tag_config("keyword", foreground=SYNTAX_KEYWORDS_COLOR)
    right_text.tag_config("keyword", foreground=SYNTAX_KEYWORDS_COLOR)

    left_text.tag_config("op", foreground=SYNTAX_OPERATIONS_COLOR)
    right_text.tag_config("op", foreground=SYNTAX_OPERATIONS_COLOR)

    left_text.tag_config("dot", foreground=SYNTAX_OPERATIONS_COLOR)
    right_text.tag_config("dot", foreground=SYNTAX_OPERATIONS_COLOR)

    left_text.tag_config("string", foreground=SYNTAX_STRINGS_COLOR)
    right_text.tag_config("string", foreground=SYNTAX_STRINGS_COLOR)

    left_text.tag_config("numeral", foreground=SYNTAX_NUMBERS_COLOR)
    right_text.tag_config("numeral", foreground=SYNTAX_NUMBERS_COLOR)

    left_text.tag_config("id", foreground=SYNTAX_NAMES_COLOR)
    right_text.tag_config("id", foreground=SYNTAX_NAMES_COLOR)

    left_text.tag_config("function", foreground=SYNTAX_FUNCTIONS_COLOR)
    right_text.tag_config("function", foreground=SYNTAX_FUNCTIONS_COLOR)

    job = None

    def index_in_tag_range(text_widget, tag, index):
        """
        Returns (start, end) of the tag range containing index,
        or None if not inside the tag.
        """

        # Find the first tag range that starts at or after index
        start = text_widget.tag_prevrange(tag, index)

        if not start:
            return None

        tag_start, tag_end = start

        if text_widget.compare(tag_start, "<=", index) and text_widget.compare(
            index, "<", tag_end
        ):
            return tag_start, tag_end

        return None

    def syntax_highlight(text_widget, tk_start_ind, tk_end_ind):
        for start_offset, end_offset, tag_type in LuaObject.syntax_highlight_iter(
            text_widget.get(tk_start_ind, tk_end_ind)
        ):
            s = f"{tk_start_ind} + {start_offset} chars"
            e = f"{tk_start_ind} + {end_offset} chars"
            text_widget.tag_add(tag_type, s, e)

    def highlight_visible_left():
        # Get visible area and extend it in case of multiline lexems on borders
        start = left_text.index("@0,0")

        if extended_start := index_in_tag_range(left_text, "comment", start):
            start, _ = extended_start

        end = left_text.index(f"@0,{left_text.winfo_height()}")

        if extended_end := index_in_tag_range(left_text, "comment", end):
            _, end = extended_end

        for tag in syntax_highlight_tags:
            left_text.tag_remove(tag, start, end)

        syntax_highlight(left_text, start, end)

    def schedule_highlight(event=None, dur=50):
        nonlocal job
        if job:
            root.after_cancel(job)
        job = root.after(dur, highlight_visible_left)

    def highlight_debug(
        text_widget, start_offset: int, end_offset: int, tag_name="highlight"
    ):
        start_index = text_widget.index(f"1.0 + {start_offset} chars")
        end_index = text_widget.index(f"1.0 + {end_offset} chars")

        text_widget.tag_remove(tag_name, "1.0", "end")
        text_widget.tag_add(tag_name, start_index, end_index)

        # ensure visible
        text_widget.see(start_index)

        # center the highlighted region
        bbox = text_widget.bbox(start_index)
        if bbox is None:
            return

        y = bbox[1]
        line_height = bbox[3]
        widget_height = text_widget.winfo_height()

        # scroll so highlight is centered
        text_widget.yview_scroll(int((y - widget_height / 2) / line_height), "units")

    # textbox ivents
    def handle_paste(event):
        widget = event.widget

        try:
            clipboard_text = root.clipboard_get()
        except TclError:
            return "break"

        if widget.tag_ranges("sel"):
            selected = widget.index("sel.first")
            widget.delete("sel.first", "sel.last")
            widget.insert("insert", clipboard_text)
        else:
            widget.insert("insert", clipboard_text)

        return "break"

    def on_text_change(event):
        left_text.tag_remove("highlight", "1.0", "end")
        left_text.edit_modified(False)
        right_text.tag_remove("highlight", "1.0", "end")
        right_text.edit_modified(False)

    def handle_left_text_click(event):
        update_cursor(left_text)

    def handle_right_text_click(event):
        update_cursor(right_text)

        code = left_text.get("1.0", "end-1c")
        res = right_text.get("1.0", "end-1c")

        if (
            hash(code) == left_text_hash
            and hash(res) == right_text_hash
            and right_text_map is not None
        ):
            tmp = right_text.count("1.0", INSERT, "chars")
            offset = tmp[0] if tmp is not None else 0
            m = right_text_map.map(offset)
            highlight_debug(right_text, m[2], m[3])
            highlight_debug(left_text, m[0], m[1])

    # actions
    def sync_scroll(*args):
        schedule_highlight(dur=20)
        update_line_numbers()

    def update_line_numbers(event=None):
        line_numbers.delete("all")

        i = left_text.index("@0,0")

        while True:
            dline = left_text.dlineinfo(i)
            if dline is None:
                break

            y = dline[1]
            line_number = i.split(".")[0]

            line_numbers.create_text(
                35,
                y,
                anchor="ne",
                text=line_number,
                fill="#aaaaaa",
                font=text_font,
            )

            i = left_text.index(f"{i}+1line")

    def update_cursor(text_widget, event=None):
        line, col = text_widget.index(INSERT).split(".")
        cursor_label.config(text=f"Line: {line}, Col: {int(col)+1}")

    def set_right_text(text: str, is_error: bool = False):
        right_text.config(state="normal")
        right_text.delete("1.0", END)
        right_text.insert(END, text)

        for tag in right_text.tag_names():
            right_text.tag_remove(tag, "1.0", "end")

        if is_error:
            right_text.config(fg="red")
        else:
            right_text.config(fg="#aaaaaa")
            syntax_highlight(right_text, "1.0", "end")

        right_text.config(state="disabled")

    # buttons
    def minify_code():
        nonlocal left_text_hash
        nonlocal right_text_hash
        nonlocal right_text_map
        try:
            code = left_text.get("1.0", "end-1c")
            l_obj = LuaObject(code)
            # l_obj.show_ast()
            l_obj.do_renaming()
            result_map = l_obj.text()
            result = result_map.text

            set_right_text(result)

            orig_len_label.config(text=f"Original length: {len(code)}")
            rev_len_label.config(text=f"Minified length: {len(result)}")
            prop_label.config(
                text=f"Proportion: {len(code)/len(result) if code else 0:.2f}"
            )

            left_text_hash = hash(code)
            right_text_hash = hash(result)
            right_text_map = result_map

        except ParsingError as e:
            set_right_text(str(e), is_error=True)
        except Exception as e:
            set_right_text(str(format_exc()), is_error=True)

        update_cursor(left_text)
        update_line_numbers()

    def copy_result():
        root.clipboard_clear()
        root.clipboard_append(right_text.get("1.0", "end-1c"))

    def increase_font():
        size = text_font.cget("size")
        text_font.configure(size=size + 1)

    def decrease_font():
        size = text_font.cget("size")
        if size > 6:
            text_font.configure(size=size - 1)

    def normal_font():
        text_font.configure(size=12)

    button_width = 16
    reverse_button = Button(
        center_frame,
        text="Minify",
        width=button_width,
        bg="#4caf50",
        fg="white",
        font=button_font,
        command=minify_code,
    )
    reverse_button.grid(row=3, column=0, pady=(0, 5))
    copy_button = Button(
        center_frame,
        text="Copy Result",
        width=button_width,
        bg="#2196f3",
        fg="white",
        font=button_font,
        command=copy_result,
    )
    copy_button.grid(row=4, column=0, pady=(0, 10))

    # menu bar
    menu_bar = Menu(root, bg=APP_MAIN_BG, fg="white", borderwidth=0)
    root.config(menu=menu_bar)
    view_menu = Menu(menu_bar, tearoff=0, bg=APP_MAIN_BG)

    view_menu.add_command(label="Zoom In", command=increase_font)
    view_menu.entryconfig(0, foreground="white")

    view_menu.add_command(label="Zoom Out", command=decrease_font)
    view_menu.entryconfig(1, foreground="white")

    view_menu.add_command(label="Normal Size", command=normal_font)
    view_menu.entryconfig(2, foreground="white")

    menu_bar.add_cascade(label="View", menu=view_menu)

    # context menu
    def show_menu(event, widget):
        menu = Menu(
            root, tearoff=0, bg="#333333", fg="white", activebackground="#555555"
        )
        menu.add_command(
            label="Copy", command=lambda: widget.event_generate("<<Copy>>")
        )
        menu.add_command(
            label="Paste", command=lambda: widget.event_generate("<<Paste>>")
        )
        menu.add_command(
            label="Select All", command=lambda: widget.tag_add("sel", "1.0", "end")
        )
        menu.tk_popup(event.x_root, event.y_root)

    # bindings
    left_text.bind("<<Paste>>", handle_paste)
    right_text.bind("<<Paste>>", handle_paste)

    left_text.bind("<Button-3>", lambda e: show_menu(e, left_text))
    right_text.bind("<Button-3>", lambda e: show_menu(e, right_text))

    left_text.bind(
        "<KeyRelease>", lambda e: (update_line_numbers(), update_cursor(left_text))
    )
    left_text.bind("<ButtonRelease-1>", handle_left_text_click)
    right_text.bind("<ButtonRelease-1>", handle_right_text_click)

    left_text.bind(
        "<<Modified>>", lambda e: (on_text_change(e), schedule_highlight(dur=100))
    )
    right_text.bind("<<Modified>>", on_text_change)

    left_text.bind(
        "<MouseWheel>", lambda e: (update_line_numbers, schedule_highlight(dur=30))
    )
    left_text.bind(
        "<Configure>", lambda e: (update_line_numbers, schedule_highlight(dur=30))
    )

    # scaling
    root.rowconfigure(0, weight=1)
    left_frame.columnconfigure(1, weight=1)
    root.columnconfigure(1, weight=0)
    root.columnconfigure(2, weight=1)

    right_text_hash = hash("")
    right_text_map = None
    left_text_hash = hash("")

    update_line_numbers()
    update_cursor(left_text)

    root.mainloop()
