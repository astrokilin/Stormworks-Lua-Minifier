import re
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
    Menubutton,
)

from lua import LuaObject, ParsingError

APP_MAIN_BG = "#2b2b2b"


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

    line_numbers = Text(
        left_frame,
        width=4,
        padx=4,
        pady=4,
        bg=APP_MAIN_BG,
        fg="#aaaaaa",
        font=text_font,
        state="disabled",
        relief="flat",
        bd=0,
    )
    line_numbers.pack(side="left", fill="y")

    left_text = Text(
        left_frame,
        bg="#1e1e1e",
        fg="#ffffff",
        insertbackground="red",
        font=text_font,
        undo=True,
    )
    left_text.pack(side="left", fill="both", expand=True)
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
    output_text = Text(root, bg="#1a1a1a", fg="#aaaaaa", font=text_font)
    output_text.grid(row=0, column=2, sticky="nsew", padx=10, pady=10)
    root.columnconfigure(2, weight=1)

    # scrollbar stuff
    scrollbar = Scrollbar(left_frame)
    scrollbar.pack(side="right", fill="y")
    left_text.config(
        yscrollcommand=lambda *args: (scrollbar.set(*args), sync_scroll(*args))
    )
    line_numbers.config(yscrollcommand=scrollbar.set)
    scrollbar.config(
        command=lambda *args: (left_text.yview(*args), line_numbers.yview(*args))
    )

    # actions
    def sync_scroll(*args):
        line_numbers.yview_moveto(left_text.yview()[0])

    def update_line_numbers(event=None):
        line_numbers.config(state="normal")
        line_numbers.delete("1.0", END)
        total_lines = int(left_text.index("end-1c").split(".")[0])

        for i in range(1, total_lines + 1):
            line_numbers.insert(END, f"{i}\n")

        line_numbers.config(state="disabled")

    def update_cursor(event=None):
        line, col = left_text.index(INSERT).split(".")
        cursor_label.config(text=f"Line: {line}, Col: {int(col)+1}")

    # buttons
    def minify_code():
        try:
            code = left_text.get("1.0", "end-1c")
            l_obj = LuaObject(code)
            l_obj.do_renaming()
            result = l_obj.text()

            output_text.config(fg="#aaaaaa")
            orig_len_label.config(text=f"Original length: {len(code)}")
            rev_len_label.config(text=f"Minified length: {len(result)}")
            prop_label.config(
                text=f"Proportion: {len(code)/len(result) if code else 0:.2f}"
            )

        except ParsingError as e:
            result = (
                e.err_line
                + "\n"
                + re.sub("[^\t ]", " ", e.err_line[: e.file_pos[1] - 1])
                + "^" * e.file_pos[2]
                + "\n"
                + str(e)
            )
            output_text.config(fg="red")

        output_text.delete("1.0", END)
        output_text.insert(END, result)
        update_cursor()
        update_line_numbers()

    def copy_result():
        root.clipboard_clear()
        root.clipboard_append(output_text.get("1.0", "end-1c"))

    def increase_font():
        size = text_font.cget("size")
        text_font.configure(size=size + 1)

    def decrease_font():
        size = text_font.cget("size")
        if size > 6:
            text_font.configure(size=size - 1)

    def normal_font():
        text_font.configure(12)

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
    view_menu.add_command(label="Zoom Out", command=decrease_font)
    view_menu.add_command(label="Normal Size", command=normal_font)
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

    left_text.bind("<Button-3>", lambda e: show_menu(e, left_text))
    output_text.bind("<Button-3>", lambda e: show_menu(e, output_text))

    # bindings
    left_text.bind("<KeyRelease>", lambda e: (update_line_numbers(), update_cursor()))
    left_text.bind("<ButtonRelease-1>", lambda e: update_cursor())

    # scaling
    root.rowconfigure(0, weight=1)
    left_frame.columnconfigure(1, weight=1)
    root.columnconfigure(1, weight=0)
    root.columnconfigure(2, weight=1)

    update_line_numbers()
    update_cursor()

    root.mainloop()
