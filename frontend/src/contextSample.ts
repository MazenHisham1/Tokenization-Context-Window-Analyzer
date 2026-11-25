import type { SimMessage } from "./types";

/** A short support chat that is long enough to overflow a small window (try 300 to 400 tokens). */
export const SAMPLE_MESSAGES: SimMessage[] = [
  { role: "system", text: "You are a helpful support assistant for a small online bookshop. Answer politely and briefly. Never promise refunds." },
  { role: "user", text: "Hi! I ordered three books last week and only two arrived. The missing one is a hardcover copy of a cookbook. Can you help me find out what happened to it?" },
  { role: "assistant", text: "Sorry to hear that! Orders with several books are sometimes shipped in separate parcels, so the third book may simply still be on its way. Could you share your order number so I can check the shipping status of each parcel?" },
  { role: "user", text: "Sure, it is 48213. By the way, I also wanted to ask whether you sell gift cards, because my sister's birthday is next month and she loves reading, especially crime novels and old science fiction." },
  { role: "assistant", text: "Thanks. Order 48213 shows two parcels: one delivered on Tuesday and a second one handed to the carrier yesterday, so the cookbook should arrive within three working days. And yes, we sell digital gift cards from 10 to 100 euros; they are sent by email right after payment." },
  { role: "user", text: "Great, thank you. Last question: what is the title of the cookbook in my order, so I can be sure it is the one in the second parcel?" },
];
