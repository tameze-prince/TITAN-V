import "./globals.css";

export const metadata = {
  title: "TITAN V. Command Center",
  description: "Human operator surface for TITAN V.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
