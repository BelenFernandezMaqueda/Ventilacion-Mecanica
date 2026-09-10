import tkinter as tk

ventana = tk.Tk()
ventana.title("TEST")
ventana.geometry("500x300")

ventana.configure(bg="lightblue")

boton = tk.Button(
    ventana,
    text="HOLA 👋",
    font=("Arial", 30),
    command=ventana.destroy
)
boton.pack(expand=True)

ventana.mainloop()