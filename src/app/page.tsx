"use client";
import { useState } from "react";

export default function Home() {
  const [message, setMessage] = useState("");

  const sendMessage = async () => {
    const response = await fetch("http://localhost:8484", {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
    });
    const data = await response.json();
    setMessage(data.message);
  };

  return (
    <div className="flex h-screen w-screen justify-center items-center flex-col gap-4">
      <h1>Buddhi AI Studio</h1>
      <button onClick={sendMessage} className="bg-blue-500 text-white px-4 py-2 rounded-md">
        Send Message
      </button>
      <p>Message: {message}</p>
    </div>
  );
}
