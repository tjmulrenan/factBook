import json
import os
from tkinter import Tk, Label, Text, Button, Listbox, END, Frame, messagebox, filedialog, StringVar
from tkinter import ttk
from ttkthemes import ThemedTk  # if using themed root
import time  # if you're using autosave timestamps

# 🔽 Add color constants here
BG_DARK = "#2e2e2e"
FG_LIGHT = "#f0f0f0"
ENTRY_BG = "#3c3c3c"
HIGHLIGHT_BORDER = "#66aaff"
HIGHLIGHT_BG = "#44475a"

class FactEditorApp:
    def __init__(self, root, original_facts, edited_facts, file_path):
        # 🔹 Core setup
        self.root = root
        self.index = 0
        self.original_facts = original_facts
        self.facts = edited_facts
        self.edited_file_path = file_path

        # 🔹 Category & state tracking
        self.category_var = StringVar()
        self.category_counts = self.count_categories()
        self.has_saved_field = set()
        self.has_modified_category = set()
        self.original_view_state = {}
        self.field_cache = {}
        self.deleted_facts = []

        # 🔹 Autosave state
        self.typing_timers = {}
        self.typing_timer = None
        self.last_typed_field = None
        self.autosave_interval_ms = 10000  # 10 seconds

        # 🔹 UI state
        self.save_indicators = {}

        # 🔹 Build UI
        self.bonus_label_text = "Bonus Fact"  # default fallback label
        self.create_widgets()
        self.display_fact()

        # 🔹 Autosave loop
        self.start_autosave()

        # 🔹 Final UI layout tweaks
        self.root.update_idletasks()  # Allow geometry to compute
        self.root.minsize(self.root.winfo_reqwidth(), self.root.winfo_reqheight())  # Set min size
        self.root.geometry("")  # Let it resize naturally

    def on_focus_in(self, widget):
        widget.config(highlightthickness=2, highlightbackground=HIGHLIGHT_BORDER)

    def on_focus_out(self, widget):
        widget.config(highlightthickness=0)

    def on_category_change(self, event=None):
        fact = self.facts[self.index]
        old_cat = self.current_category()
        new_cat = self.category_var.get()

        if old_cat == new_cat:
            return

        if fact.get("approved"):
            messagebox.showinfo("Locked", "Approved facts can't change category.")
            self.category_var.set(old_cat)
            return

        # Update counts
        self.update_category_count(old_cat, -1)
        self.update_category_count(new_cat, +1)

        # Save modified category
        fact["categories"] = [new_cat]
        self.has_modified_category.add(self.index)

        # Refresh listbox
        self.refresh_category_listbox()

        # Only show buttons if it's been manually changed AND differs from original
        original = self.original_facts[self.index].get("categories", [None])[0]
        if new_cat != original and self.index in self.has_modified_category:
            self.category_toggle_btn.pack(side="left", padx=6)
            self.category_reset_btn.pack(side="left", padx=10)
        else:
            self.category_toggle_btn.pack_forget()
            self.category_reset_btn.pack_forget()


    
    def reset_category(self):
        original = self.original_facts[self.index].get("categories", [None])[0]
        current = self.category_var.get()

        if original == current:
            return

        if not self.confirm("Reset Category", f"Reset category to '{original}'?"):
            return

        # Update counts
        self.update_category_count(current, -1)
        self.update_category_count(original, +1)

        # Set category back to original
        self.category_var.set(original)
        self.facts[self.index]["categories"] = [original]

        # Remove this fact index from the modified category set
        if self.index in self.has_modified_category:
            self.has_modified_category.remove(self.index)

        # Refresh the category count listbox
        self.refresh_category_listbox()

        # Hide buttons since it's now matching the original
        self.category_toggle_btn.pack_forget()
        self.category_reset_btn.pack_forget()




    def reset_field(self, field):
        if not self.confirm("Reset Field", f"Are you sure you want to reset '{field}' to its original value?"):
            return

        original_value = self.original_facts[self.index].get(field, "")

        if field == "activity_choices":
            for i, entry in enumerate(self.fields[field]):
                entry.delete("1.0", END)
                if isinstance(original_value, list) and i < len(original_value):
                    entry.insert("1.0", original_value[i])
        else:
            self.fields[field].delete("1.0", END)
            self.fields[field].insert("1.0", original_value)

        self.fields[field].config(state="normal", bg=ENTRY_BG, fg=FG_LIGHT, insertbackground=FG_LIGHT)
        self.toggle_buttons[field]["text"] = "See Original"
        self.reset_buttons[field].pack(side="left", padx=6)

    def on_typing(self, field):
        self.last_typed_field = field
        self.schedule_autosave_after_typing(field)

    def schedule_autosave_after_typing(self, field):
        # Cancel only the timer for this specific field
        if field in self.typing_timers:
            self.root.after_cancel(self.typing_timers[field])

        # Schedule new save for this field only
        self.typing_timers[field] = self.root.after(1500, lambda: self.save_current_fact(field))

    def save_current_fact(self, field=None):
        self.facts[self.index] = self.get_edited_fact()
        self.export_facts()
        current_time = time.strftime("%H:%M:%S")
        self.autosave_label.config(text=f"💾 Autosaved at {current_time}")
        self.root.after(3000, lambda: self.autosave_label.config(text=""))

        if field:
            self.has_saved_field.add(field)

            if field.startswith("activity_choices"):
                base_field = "activity_choices"
                original_val = self.original_facts[self.index].get(base_field, [])
                current_val = self.facts[self.index].get(base_field, [])
                is_diff = original_val != current_val
                if is_diff:
                    self.toggle_buttons[base_field].pack(side="left", padx=6)
                    self.reset_buttons[base_field].pack(side="left", padx=6)
                else:
                    self.toggle_buttons[base_field].pack_forget()
                    self.reset_buttons[base_field].pack_forget()
            else:
                original_val = self.original_facts[self.index].get(field, "")
                current_val = self.facts[self.index].get(field, "")
                is_diff = original_val != current_val
                if is_diff:
                    self.toggle_buttons[field].pack(side="left", padx=6)
                    self.reset_buttons[field].pack(side="left", padx=6)
                else:
                    self.toggle_buttons[field].pack_forget()
                    self.reset_buttons[field].pack_forget()

            tick = self.save_indicators.get(field)
            if tick:
                tick.place(relx=1.0, rely=0.0, anchor="ne")
                tick.lift()
                self.root.after(2000, lambda t=tick: t.place_forget())

            if field in self.typing_timers:
                del self.typing_timers[field]



    def count_categories(self):
        counts = {}
        for fact in self.facts:
            for category in fact.get("categories", []):
                counts[category] = counts.get(category, 0) + 1
        return counts

    def get_available_categories(self):
        current = self.current_category()
        return sorted([
            cat for cat, count in self.category_counts.items()
            if count < 20 or cat == current
        ])

    def current_category(self):
        return self.facts[self.index].get("categories", [None])[0]
    
    def toggle_category(self):
        current = self.category_var.get()
        original = self.original_facts[self.index].get("categories", [None])[0]

        if getattr(self, "showing_original_category", False):
            self.category_var.set(self.facts[self.index].get("categories", [None])[0])
            self.category_menu.config(state="readonly")
            self.category_toggle_btn.config(text="See Original")
            self.showing_original_category = False
        else:
            self.category_var.set(original)
            self.category_menu.config(state="disabled")  # 👈 This triggers yellow/black via style
            self.category_toggle_btn.config(text="See Modified")
            self.showing_original_category = True

    def update_category_count(self, cat, delta):
        if not cat:
            return
        self.category_counts[cat] = max(0, self.category_counts.get(cat, 0) + delta)

    def refresh_category_listbox(self):
        self.cat_listbox.delete(0, END)
        current = self.current_category()

        for cat, count in sorted(self.category_counts.items()):
            label = f"{cat}: {count}"
            self.cat_listbox.insert(END, label)
            idx = self.cat_listbox.size() - 1

            color = 'red' if count < 3 else FG_LIGHT
            self.cat_listbox.itemconfig(idx, {'fg': color})

            bg_color = '#555555' if cat == current else ENTRY_BG
            self.cat_listbox.itemconfig(idx, {'bg': bg_color})

    def reset_all_facts(self):
        confirm = messagebox.askyesno("Reset All", "Are you sure you want to reset all facts to their original versions?")
        if not confirm:
            return

        self.facts = json.loads(json.dumps(self.original_facts))  # Deep copy
        self.index = 0
        self.category_counts = self.count_categories()
        self.display_fact()
        self.refresh_category_listbox()

    def remove_fact(self):
        if self.index >= len(self.facts):
            return

        confirm = messagebox.askyesno("Remove Fact", "Are you sure you want to delete this fact?")
        if not confirm:
            return

        fact = self.facts[self.index]
        category = fact.get("categories", [None])[0]

        self.update_category_count(category, -1)

        del self.facts[self.index]  # ✅ only remove from edited facts

        if self.index >= len(self.facts):
            self.index = max(0, len(self.facts) - 1)

        self.export_facts()
        self.display_fact()
        self.refresh_category_listbox()



    def create_widgets(self):
        self.root.title(f"Fact Fiddler 5000 - {os.path.basename(self.edited_file_path)}")
        self.reset_buttons = {}

        # === LEFT PANEL: Category Counts + Buttons ===
        self.left_frame = Frame(self.root, bg=BG_DARK)
        self.left_frame.pack(side="left", padx=10, pady=10, anchor="n")

        Label(self.left_frame, text="Category Counts", bg=BG_DARK, fg=FG_LIGHT, font=("Arial", 18, "bold")).pack(anchor="w", pady=(0, 4))

        cat_frame = Frame(self.left_frame, bg=BG_DARK)
        cat_frame.pack(anchor="w")

        visible_items = min(len(self.category_counts), 12)
        self.cat_listbox = Listbox(
            cat_frame,
            width=35,
            height=visible_items,
            bg=ENTRY_BG,
            fg=FG_LIGHT,
            font=("Arial", 14)  # ~75% larger than default size ~8-10
        )
        self.cat_listbox.pack(side="left", fill="y")

        if len(self.category_counts) > 12:
            cat_scroll = ttk.Scrollbar(cat_frame, orient="vertical", command=self.cat_listbox.yview)
            cat_scroll.pack(side="right", fill="y")
            self.cat_listbox.config(yscrollcommand=cat_scroll.set)

        self.refresh_category_listbox()  # 🔁 Use the centralized method for listbox updates

        # 🔽 Add bottom controls underneath category list
        self.bottom_frame = Frame(self.left_frame, bg=BG_DARK)
        self.bottom_frame.pack(pady=10)
        self.progress_label = Label(self.bottom_frame, text="", font=("Arial", 10, "italic"), bg=BG_DARK, fg=FG_LIGHT)
        self.progress_label.pack(side="top", pady=(0, 3))

        self.approval_summary_label = Label(self.bottom_frame, text="", font=("Arial", 10), fg="lightgreen", bg=BG_DARK)
        self.approval_summary_label.pack(side="top", pady=(0, 6))

        self.autosave_label = Label(self.bottom_frame, text="", font=("Arial", 9), fg="green", bg=BG_DARK)
        self.autosave_label.pack(pady=(0, 8))

        self.button_top = Frame(self.bottom_frame, bg=BG_DARK)
        self.button_top.pack()

        # 🧭 Navigation buttons
        self.button_top = Frame(self.bottom_frame, bg=BG_DARK)
        self.button_top.pack(pady=(0, 8))  # bottom padding only
        Button(self.button_top, text="⬅ Back", width=14, command=self.go_back, bg=ENTRY_BG, fg=FG_LIGHT, activebackground="#555").pack(side="left", padx=10)
        Button(self.button_top, text="➡ Next", width=14, command=self.go_next, bg=ENTRY_BG, fg=FG_LIGHT, activebackground="#555").pack(side="left", padx=10)

        # 🔲 Button Row 1: Restore, Remove, Approve
        self.button_bottom = Frame(self.bottom_frame, bg=BG_DARK)
        self.button_bottom.pack(pady=(0, 8))  # even spacing like top

        self.restore_button = Button(self.button_bottom, text="🔁 Restore Fact", width=14, command=self.show_restore_popup, bg=ENTRY_BG, fg=FG_LIGHT, activebackground="#555")
        self.restore_button.pack(side="left", padx=10)

        Button(self.button_bottom, text="❌ Remove", width=14, command=self.remove_fact, bg=ENTRY_BG, fg=FG_LIGHT, activebackground="#555").pack(side="left", padx=10)

        self.approve_button = Button(self.button_bottom, text="✅ Approve", width=14, command=self.toggle_approval, bg=ENTRY_BG, fg=FG_LIGHT, activebackground="#555")
        self.approve_button.pack(side="left", padx=10)

        # 🔲 Button Row 2: Reset All, Reset File
        self.button_bottom_lower = Frame(self.bottom_frame, bg=BG_DARK)
        self.button_bottom_lower.pack()  # no padding needed here, already above had (0, 8)

        self.reset_entire_button = Button(self.button_bottom_lower, text="🔁 Reset All", width=14, command=self.reset_entire_fact, bg=ENTRY_BG, fg=FG_LIGHT, activebackground="#555")
        self.reset_entire_button.pack(side="left", padx=10)

        self.reset_file_button = Button(self.button_bottom_lower, text="🗑️ Reset File", width=14, command=self.reset_entire_file, bg="#aa3333", fg="white", activebackground="#662222")
        self.reset_file_button.pack(side="left", padx=10)



        # === RIGHT PANEL: Fact Fields ===
        self.right_frame = Frame(self.root, bg=BG_DARK)
        self.right_frame.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        self.fields = {}
        field_names = [
            ("title", 2), ("story", 6), ("activity_question", 3),
            ("activity_choices", 4), ("activity_answer", 3), ("bonus_fact", 3)
        ]


        self.toggle_buttons = {}

        for i, (field, height) in enumerate(field_names):
            field_frame = Frame(self.right_frame, bg=BG_DARK)
            field_frame.pack(fill="x", padx=8, pady=8, anchor="w")

            label_frame = Frame(field_frame, bg=BG_DARK)
            label_frame.pack(fill="x")

            label_text = "Bonus Fact" if field == "bonus_fact" else field.replace("_", " ").title()
            label_widget = Label(label_frame, text=label_text, anchor="w", font=("Arial", 10, "bold"),
                                bg=BG_DARK, fg=FG_LIGHT)
            label_widget.pack(side="left")

            if field == "bonus_fact":
                self.bonus_label_widget = label_widget  # ✅ Save it so we can change it later

            if field != "activity_choices":
                txt = Text(field_frame, height=height, width=100, wrap="word", font=("Arial", 10),
                        bg=ENTRY_BG, fg=FG_LIGHT, insertbackground=FG_LIGHT, relief="flat", highlightthickness=0)
                txt.bind("<FocusIn>", lambda e, w=txt: self.on_focus_in(w))
                txt.bind("<FocusOut>", lambda e, w=txt: self.on_focus_out(w))
                txt.pack(fill="x", pady=(2, 0))
                txt.bind("<KeyRelease>", lambda e, f=field: self.on_typing(f))
                self.fields[field] = txt

                tick = Label(txt, text="✅", bg=ENTRY_BG, fg="lightgreen", font=("Arial", 10))
                tick.place(relx=1.0, rely=0.0, anchor="ne")
                tick.place_forget()
                self.save_indicators[field] = tick

            toggle_btn = Button(label_frame, text="See Original", font=("Arial", 8),
                                command=lambda f=field: self.toggle_field(f, self.fields[f]))
            toggle_btn.pack(side="left", padx=6)
            self.toggle_buttons[field] = toggle_btn

            reset_btn = Button(label_frame, text="Reset to Original", font=("Arial", 8),
                            command=lambda f=field: self.reset_field(f))
            reset_btn.pack(side="left", padx=6)
            reset_btn.pack_forget()
            self.reset_buttons[field] = reset_btn


            # Now actual field entry
            if field == "activity_choices":
                self.fields[field] = []
                for j in range(4):
                    entry = Text(field_frame, height=1, width=100, font=("Arial", 10),
                                bg=ENTRY_BG, fg=FG_LIGHT, insertbackground=FG_LIGHT, relief="flat", highlightthickness=0)
                    entry.bind("<FocusIn>", lambda e, w=entry: self.on_focus_in(w))
                    entry.bind("<FocusOut>", lambda e, w=entry: self.on_focus_out(w))
                    entry.pack(fill="x", pady=2)
                    entry.bind("<KeyRelease>", lambda e, f=field, i=j: self.on_typing(f"{f}_{i}"))
                    self.fields[field].append(entry)

                    tick = Label(entry, text="✅", bg=ENTRY_BG, fg="lightgreen", font=("Arial", 10))
                    tick.place(relx=1.0, rely=0.0, anchor="ne")
                    tick.place_forget()
                    self.save_indicators[f"{field}_{j}"] = tick

        # === CATEGORY SELECTOR ===
        Label(self.right_frame, text="Category", font=("Arial", 10, "bold"), bg=BG_DARK, fg=FG_LIGHT).pack(
            anchor="w", padx=5, pady=(10, 2)
        )

        cat_row_frame = Frame(self.right_frame, bg=BG_DARK)
        cat_row_frame.pack(anchor="w", padx=5, pady=(0, 5))
        
        for widget in cat_row_frame.winfo_children():
            print(widget, widget.winfo_class())

        # Category dropdown
        self.category_menu = ttk.Combobox(cat_row_frame, textvariable=self.category_var, state="readonly", width=50)
        self.category_menu.pack(side="left")

        # 🔽 ⬇️ INSERT THE STYLE OVERRIDE HERE
        style = ttk.Style()
        style.theme_use("default")  # or "equilux" if you prefer to keep it themed

        style.map('Custom.TCombobox',
            fieldbackground=[('disabled', '#fff89e')],
            foreground=[('disabled', 'black')],
        )

        style.configure("Custom.TCombobox",
            selectbackground=ENTRY_BG,
            selectforeground=FG_LIGHT,
            fieldbackground=ENTRY_BG,
            foreground=FG_LIGHT,
            font=("Arial", 10)
        )

        self.category_menu.configure(style="Custom.TCombobox")

        # Bind category change detection
        self.category_menu.bind("<<ComboboxSelected>>", self.on_category_change)

        # Reset to original button
        self.category_reset_btn = Button(cat_row_frame, text="Reset to Original", font=("Arial", 8),
                                        command=self.reset_category)
        self.category_reset_btn.pack(side="left", padx=10)

        self.category_toggle_btn = Button(cat_row_frame, text="See Original", font=("Arial", 8),
                                  command=self.toggle_category)
        self.category_toggle_btn.pack(side="left", padx=6)



        self.root.update()
        self.root.focus_force()


    def reset_entire_file(self):
        if not self.confirm(
            "Reset All Facts", 
            "⚠️ This will reset ALL facts to their original versions and remove ALL edits and approvals. Are you sure?"
        ):
            return

        self.facts = []
        for fact in self.original_facts:
            fact_copy = fact.copy()
            fact_copy["approved"] = False
            self.facts.append(fact_copy)

        self.index = 0

        # 🔁 Reset category counts properly
        self.category_counts = self.count_categories()

        self.export_facts()
        self.display_fact()

        # 🔁 Refresh the category count list display
        self.refresh_category_listbox()

        messagebox.showinfo("Reset Complete", "All facts have been reset to their original versions.")



    def reset_entire_fact(self):
        if not self.confirm("Reset Entire Fact", "Are you sure you want to reset all fields to their original values? This will overwrite your changes."):
            return

        current_fact = self.facts[self.index]
        original_fact = self.original_facts[self.index]

        current_cat = current_fact.get("categories", [None])[0]
        original_cat = original_fact.get("categories", [None])[0]

        # Update category counts
        self.update_category_count(current_cat, -1)
        self.update_category_count(original_cat, +1)

        # Replace the fact and clear approval
        self.facts[self.index] = original_fact.copy()
        self.facts[self.index]["approved"] = False

        self.export_facts()
        self.display_fact()

        # Update category list display
        self.refresh_category_listbox()



    def toggle_approval(self):
        fact = self.facts[self.index]
        cat = self.category_var.get()
        current_cat = self.current_category()

        if fact.get("approved"):
            # Unapprove
            fact["approved"] = False
            self.update_category_count(cat, -1)
            self.export_facts()
        else:
            # Approve
            if not cat:
                messagebox.showerror("Error", "Please select a category.")
                return
            if self.category_counts.get(cat, 0) >= 20 and cat != current_cat:
                messagebox.showerror("Error", f"Category '{cat}' already has 20 items.")
                return
            fact["approved"] = True
            fact["categories"] = [cat]
            self.update_category_count(cat, +1)
            self.export_facts()

        self.display_fact()  # Refresh everything including the button text and progress label


    def toggle_field(self, field, widget):
        fact_index = self.index
        original_value = self.original_facts[fact_index].get(field, "")
        edited_value = self.facts[fact_index].get(field, "")

        # 🔍 DEBUG
        print(f"[DEBUG] Field: {field}")
        print(f"[DEBUG] ORIGINAL: {original_value}")
        print(f"[DEBUG] MODIFIED: {edited_value}")

        # 🔄 Flip and store view state
        currently_showing_original = self.original_view_state.get(field, False)
        now_showing_original = not currently_showing_original
        self.original_view_state[field] = now_showing_original

        if field == "activity_choices":
            for i, entry in enumerate(widget):
                if now_showing_original:
                    # Cache modified values
                    if field not in self.field_cache:
                        self.field_cache[field] = [e.get("1.0", "end-1c").strip() for e in widget]

                    # Load original
                    target = original_value[i] if isinstance(original_value, list) and i < len(original_value) else ""

                    # Update content first
                    entry.config(state="normal")
                    entry.delete("1.0", END)
                    entry.insert("1.0", target)

                    # Then style and disable
                    entry.config(state="disabled", bg="#fff89e", fg="black", insertbackground="black")
                else:
                    # Load cached modified version
                    modified_list = self.field_cache.get(field, [])
                    target = modified_list[i] if i < len(modified_list) else ""

                    entry.config(state="normal", bg=ENTRY_BG, fg=FG_LIGHT, insertbackground=FG_LIGHT)
                    entry.delete("1.0", END)
                    entry.insert("1.0", target)

        else:
            if now_showing_original:
                # Cache modified version
                self.field_cache[field] = widget.get("1.0", "end-1c").strip()

                # Load original, insert it while still enabled
                widget.config(state="normal")
                widget.delete("1.0", END)
                widget.insert("1.0", original_value)

                # Then apply styling and disable
                widget.config(state="disabled", bg="#fff89e", fg="black", insertbackground="black")
            else:
                # Load cached modified version
                target = self.field_cache.get(field, "")
                widget.config(state="normal", bg=ENTRY_BG, fg=FG_LIGHT, insertbackground=FG_LIGHT)
                widget.delete("1.0", END)
                widget.insert("1.0", target)

        # Update button label and reset visibility
        if now_showing_original:
            self.toggle_buttons[field]["text"] = "See Modified"
            self.reset_buttons[field].pack_forget()
        else:
            self.toggle_buttons[field]["text"] = "See Original"
            self.reset_buttons[field].pack(side="left", padx=6)

    def display_fact(self):
        self.field_cache.clear()
        self.original_view_state.clear()

        for tick in self.save_indicators.values():
           tick.place_forget()

        if self.index >= len(self.facts):
            self.progress_label.config(text=f"Fact {self.index} / {len(self.facts)}")
            messagebox.showinfo("Done", "No more facts to review.")
            return

        fact = self.facts[self.index]
    
        # Determine custom label for bonus_fact field 
        self.bonus_label_text = "Bonus Fact"
        # Handle alternate key for follow-up question
        if fact.get("optional_type") == "follow_up_question":
            self.bonus_label_text = "Follow-Up Question"
            # Copy the actual content from follow_up_question into bonus_fact
            self.bonus_label_widget.config(text="Follow-Up Question")
            fact["bonus_fact"] = fact.get("follow_up_question", "")
        else:
            self.bonus_label_text = "Bonus Fact"
            self.bonus_label_widget.config(text="Bonus Fact")

        for field, widget in self.fields.items():
            edited_val = fact.get(field, "")
            original_val = self.original_facts[self.index].get(field, "")

            # Reset toggle state and button label for this field
            self.original_view_state[field] = False
            if field in self.toggle_buttons:
                self.toggle_buttons[field]["text"] = "See Original"

            if field == "activity_choices":
                for i, entry in enumerate(widget):
                    entry.config(state="normal", bg=ENTRY_BG, fg=FG_LIGHT, insertbackground=FG_LIGHT)
                    entry.delete("1.0", END)
                    if isinstance(edited_val, list) and i < len(edited_val):
                        entry.insert("1.0", edited_val[i])
                is_diff = edited_val != original_val
            else:
                widget.config(state="normal", bg=ENTRY_BG, fg=FG_LIGHT, insertbackground=FG_LIGHT)
                widget.delete("1.0", END)
                if isinstance(edited_val, list):
                    edited_val = ", ".join(edited_val)
                widget.insert("1.0", edited_val)
                is_diff = edited_val != original_val

            # Show or hide toggle/reset buttons based on diff
            if field in self.toggle_buttons:
                if is_diff and field in self.has_saved_field:
                    if not self.toggle_buttons[field].winfo_ismapped():
                        self.toggle_buttons[field].pack(side="left", padx=6)
                    if not self.reset_buttons[field].winfo_ismapped():
                        self.reset_buttons[field].pack(side="left", padx=6)
                else:
                    self.toggle_buttons[field].pack_forget()
                    self.reset_buttons[field].pack_forget()

        self.category_menu['values'] = self.get_available_categories()
        current = self.current_category()
        self.category_var.set(current if current in self.category_menu['values'] else "")

        # 🔁 Reset category toggle view
        current = self.current_category()
        original = self.original_facts[self.index].get("categories", [None])[0]
        self.category_var.set(current if current in self.category_menu['values'] else "")
        self.showing_original_category = False
        self.category_menu.config(state="readonly")
        self.category_toggle_btn.config(text="See Original")

        # 🔁 Show/hide category buttons based on diff
        if current != original and self.index in self.has_modified_category:
            self.category_toggle_btn.pack(side="left", padx=6)
            self.category_reset_btn.pack(side="left", padx=10)
        else:
            self.category_toggle_btn.pack_forget()
            self.category_reset_btn.pack_forget()


        # Update progress label and approve button cleanly
        status = "✅ APPROVED" if fact.get("approved") else "❌ NOT APPROVED"
        self.progress_label.config(text=f"Fact {self.index + 1} / {len(self.facts)}    {status}")

        if hasattr(self, "approve_button"):
            self.approve_button.config(text="❌ Unapprove" if fact.get("approved") else "✅ Approve")

        # ✅ Update approval summary progress (NEW)
        approved_count = sum(1 for fact in self.facts if fact.get("approved"))
        total_count = len(self.facts)
        self.approval_summary_label.config(text=f"✅ {approved_count} / {total_count} facts approved")
        self.refresh_category_listbox()  # 🔁 Re-apply highlight to the current category


    def confirm(self, title, message):
        return messagebox.askyesno(title, message)

    def get_edited_fact(self):
        edited = self.facts[self.index].copy()
        for field, widget in self.fields.items():
            if field == "activity_choices":
                edited[field] = [
                    entry.get("1.0", END).strip()
                    for entry in widget
                    if entry.get("1.0", END).strip()
                ]
            else:
                edited[field] = widget.get("1.0", END).strip()
        edited["categories"] = [self.category_var.get()]
        return edited

    def go_next(self):
        if self.index < len(self.facts) - 1:
            self.index += 1
            self.display_fact()

    def go_back(self):
        if self.index > 0:
            self.index -= 1
            self.display_fact()

    def show_restore_popup(self):
        # Get IDs of current edited facts
        existing_ids = set(fact.get("id") for fact in self.facts)

        # Find deleted facts (in original but not edited)
        deleted = [fact for fact in self.original_facts if fact.get("id") not in existing_ids]

        if not deleted:
            messagebox.showinfo("Restore Fact", "No deleted facts to restore.")
            return

        popup = Tk()
        popup.title("Restore Deleted Fact")
        popup.configure(bg=BG_DARK)

        Label(popup, text="Select a fact to restore:", bg=BG_DARK, fg=FG_LIGHT, font=("Arial", 12)).pack(pady=10)

        listbox = Listbox(popup, width=80, height=12, bg=ENTRY_BG, fg=FG_LIGHT, font=("Arial", 10))
        listbox.pack(padx=10, pady=10)

        # Track ID -> fact mapping
        id_to_fact = {}
        for fact in deleted:
            fid = str(fact.get("id", "???"))
            title = fact.get("title", "[No Title]")
            display_text = f"{fid} - {title}"
            listbox.insert(END, display_text)
            id_to_fact[display_text] = fact

        def restore_selected():
            selection = listbox.curselection()
            if not selection:
                return

            display_text = listbox.get(selection[0])
            fact = id_to_fact[display_text]

            # Insert only into the editable facts list
            insert_index = self.index + 1
            self.facts.insert(insert_index, fact.copy())

            # Update category count
            category = fact.get("categories", [None])[0]
            self.update_category_count(category, +1)

            # Refresh list and save
            self.refresh_category_listbox()
            self.export_facts()

            popup.destroy()
            messagebox.showinfo("Restored", f"Restored: {fact.get('title', 'Untitled Fact')}")



        Button(popup, text="Restore Selected", command=restore_selected, width=20, bg="#44aa44", fg="white").pack(pady=10)
        popup.mainloop()



    def approve_fact(self):
        cat = self.category_var.get()
        if not cat:
            messagebox.showerror("Error", "Please select a category.")
            return
        if self.category_counts.get(cat, 0) >= 20 and cat != self.current_category():
            messagebox.showerror("Error", f"Category '{cat}' already has 20 items.")
            return
        edited = self.get_edited_fact()
        edited["approved"] = True
        self.facts[self.index] = edited
        self.category_counts[cat] = self.category_counts.get(cat, 0) + 1
        self.export_facts()
        self.go_next()

    def export_facts(self):  # called after every save
        with open(self.edited_file_path, "w", encoding="utf-8") as f:
            json.dump(self.facts, f, indent=2)

    def start_autosave(self):
        self.export_facts()
        current_time = time.strftime("%H:%M:%S")
        self.autosave_label.config(text=f"💾 Autosaved at {current_time}")
        self.root.after(3000, lambda: self.autosave_label.config(text=""))
        self.root.after(self.autosave_interval_ms, self.start_autosave)

def load_file():
    global app  # <- ensure app is accessible globally
    path = filedialog.askopenfilename(title="Select JSON file", filetypes=[("JSON files", "*.json")])
    if not path:
        return

    base_name = os.path.basename(path)
    name, ext = os.path.splitext(base_name)
    edited_path = os.path.join(os.path.dirname(path), f"{name}_edited{ext}")

    with open(path, "r", encoding="utf-8") as f:
        original_facts = json.load(f)

    if os.path.exists(edited_path):
        with open(edited_path, "r", encoding="utf-8") as f:
            edited_facts = json.load(f)
    else:
        edited_facts = []
        for fact in original_facts:
            fact_copy = fact.copy()
            fact_copy["approved"] = False
            edited_facts.append(fact_copy)
        with open(edited_path, "w", encoding="utf-8") as f:
            json.dump(edited_facts, f, indent=2)

    app = FactEditorApp(root, original_facts, edited_facts, edited_path)



if __name__ == "__main__":
    root = ThemedTk(theme="equilux")
    root.configure(bg=BG_DARK)
    load_file()
    root.mainloop()
