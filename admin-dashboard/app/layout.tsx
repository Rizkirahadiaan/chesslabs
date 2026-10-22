import type { Metadata } from 'next';
import './globals.css';
export const metadata: Metadata = {title: 'ChessLab — Pusat Lisensi', description: 'Administrasi lisensi ChessLab PC'};
export default function RootLayout({children}: Readonly<{children: React.ReactNode}>) {
  return <html lang="id" suppressHydrationWarning><body>{children}</body></html>;
}
