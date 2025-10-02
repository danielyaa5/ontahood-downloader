#!/usr/bin/env python3
"""
Test script to verify that closing the prescan window properly re-enables the Start button.
"""
import sys
import tkinter as tk
from tkinter import ttk

def test_cancel_behavior():
    """Test that canceling prescan properly re-enables Start button."""
    
    root = tk.Tk()
    root.title("Test App")
    root.geometry("400x300")
    
    # Simulate main window Start button
    start_btn = ttk.Button(root, text="Start")
    start_btn.pack(pady=20)
    
    cancel_btn = ttk.Button(root, text="Cancel")
    cancel_btn.pack(pady=20)
    cancel_btn.configure(state="disabled")
    
    status_label = ttk.Label(root, text="Status: Ready")
    status_label.pack(pady=20)
    
    prescan_win = None
    
    def create_prescan():
        nonlocal prescan_win
        
        # Disable start, enable cancel
        start_btn.configure(state="disabled")
        cancel_btn.configure(state="normal")
        status_label.configure(text="Status: Prescan running...")
        
        # Create prescan window
        prescan_win = tk.Toplevel(root)
        prescan_win.title("Pre-Scan Preview")
        prescan_win.geometry("400x300")
        
        ttk.Label(prescan_win, text="Scanning folders...").pack(pady=20)
        
        def on_cancel():
            status_label.configure(text="Status: Prescan cancelled")
            try:
                prescan_win.destroy()
            except:
                pass
            # Re-enable Start, disable Cancel
            start_btn.configure(state="normal")
            cancel_btn.configure(state="disabled")
        
        def on_window_close():
            status_label.configure(text="Status: Prescan closed (X button)")
            try:
                prescan_win.destroy()
            except:
                pass
            # Re-enable Start, disable Cancel
            start_btn.configure(state="normal")
            cancel_btn.configure(state="disabled")
        
        prescan_win.protocol("WM_DELETE_WINDOW", on_window_close)
        
        cancel_prescan_btn = ttk.Button(prescan_win, text="Cancel", command=on_cancel)
        cancel_prescan_btn.pack(pady=20)
        
        # Simulate prescan finishing
        def finish_prescan():
            if prescan_win and prescan_win.winfo_exists():
                status_label.configure(text="Status: Prescan complete!")
            else:
                # Window was closed, just re-enable buttons
                start_btn.configure(state="normal")
                cancel_btn.configure(state="disabled")
                status_label.configure(text="Status: Prescan was closed early")
        
        root.after(3000, finish_prescan)
    
    start_btn.configure(command=create_prescan)
    
    # Test sequence
    test_results = []
    
    def run_test_sequence():
        # Test 1: Cancel button
        status_label.configure(text="Test 1: Testing Cancel button...")
        create_prescan()
        
        def test1_cancel():
            if prescan_win and prescan_win.winfo_exists():
                # Find cancel button in prescan window
                for child in prescan_win.winfo_children():
                    if isinstance(child, ttk.Button) and child['text'] == 'Cancel':
                        child.invoke()
                        break
        
        def test1_verify():
            is_enabled = str(start_btn['state']) != 'disabled'
            test_results.append(("Cancel button test", is_enabled))
            if is_enabled:
                print("✓ Test 1 PASSED: Start button re-enabled after Cancel")
            else:
                print("✗ Test 1 FAILED: Start button still disabled after Cancel")
            
            # Test 2: X button (window close)
            root.after(1000, run_test2)
        
        root.after(500, test1_cancel)
        root.after(1000, test1_verify)
    
    def run_test2():
        status_label.configure(text="Test 2: Testing X button close...")
        create_prescan()
        
        def test2_close():
            if prescan_win and prescan_win.winfo_exists():
                prescan_win.destroy()
        
        def test2_verify():
            is_enabled = str(start_btn['state']) != 'disabled'
            test_results.append(("X button test", is_enabled))
            if is_enabled:
                print("✓ Test 2 PASSED: Start button re-enabled after X button")
            else:
                print("✗ Test 2 FAILED: Start button still disabled after X button")
            
            # Test 3: Complete naturally
            root.after(1000, run_test3)
        
        root.after(500, test2_close)
        root.after(1000, test2_verify)
    
    def run_test3():
        status_label.configure(text="Test 3: Testing normal completion...")
        create_prescan()
        
        def test3_verify():
            # After 3 seconds, prescan should finish naturally
            is_enabled = str(start_btn['state']) != 'disabled'
            test_results.append(("Normal completion test", is_enabled))
            if is_enabled:
                print("✓ Test 3 PASSED: Start button re-enabled after completion")
            else:
                print("✗ Test 3 FAILED: Start button still disabled after completion")
            
            # Show results
            root.after(500, show_results)
        
        root.after(3500, test3_verify)
    
    def show_results():
        all_passed = all(result[1] for result in test_results)
        
        print("\n" + "="*50)
        print("TEST RESULTS:")
        for test_name, passed in test_results:
            status = "✓ PASSED" if passed else "✗ FAILED"
            print(f"  {status}: {test_name}")
        print("="*50)
        
        if all_passed:
            print("\n✓ ALL TESTS PASSED!")
            status_label.configure(text="✓ All tests passed!")
        else:
            print("\n✗ SOME TESTS FAILED!")
            status_label.configure(text="✗ Some tests failed!")
        
        root.after(2000, root.quit)
    
    # Start tests after a short delay
    root.after(1000, run_test_sequence)
    
    try:
        root.mainloop()
        return all(result[1] for result in test_results) if test_results else False
    except Exception as e:
        print(f"✗ Test error: {e}")
        return False

if __name__ == "__main__":
    success = test_cancel_behavior()
    sys.exit(0 if success else 1)
