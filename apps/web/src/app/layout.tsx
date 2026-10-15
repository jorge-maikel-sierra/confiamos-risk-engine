import type { Metadata } from "next";
import { Navbar } from "@/components/Navbar";
import "./globals.css";

export const metadata: Metadata = {
  title: "Confiamos Risk Engine — Cooperativa Confiamos",
  description: "Plataforma de evaluación crediticia determinística y cualitativa con IA para PyMEs",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es" className="h-full bg-slate-50">
      <body className="min-h-full flex flex-col text-slate-900 antialiased">
        <Navbar />
        <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {children}
        </main>
        <footer className="bg-white border-t border-slate-200 py-6 text-center text-xs text-slate-500">
          <p>© {new Date().getFullYear()} Cooperativa Financiera Confiamos. Motor de Riesgo y Suscripción Crediticia.</p>
        </footer>
      </body>
    </html>
  );
}
