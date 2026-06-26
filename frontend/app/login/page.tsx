"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { motion } from "motion/react";
import { supabase } from "@/lib/supabase";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { AuthVisual } from "@/components/AuthVisual";

export default function LoginPage() {
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setInfo(null);

    if (mode === "signin") {
      const { error } = await supabase.auth.signInWithPassword({ email, password });
      setLoading(false);
      if (error) {
        setError(error.message);
        return;
      }
      router.push("/plan");
    } else {
      const { data, error } = await supabase.auth.signUp({ email, password });
      setLoading(false);
      if (error) {
        setError(error.message);
        return;
      }
      if (!data.session) {
        // Email confirmation is required on this project — signUp() succeeds but
        // doesn't establish a session yet, so redirecting now would just bounce
        // straight back to /login.
        setInfo("Check your email to confirm your account, then sign in.");
        return;
      }
      router.push("/plan");
    }
  }

  return (
    <div className="mx-auto max-w-5xl px-4 py-10 lg:py-16">
      <div className="grid overflow-hidden rounded-3xl lg:min-h-[600px] lg:grid-cols-2 lg:border lg:border-white/10 lg:shadow-[0_20px_60px_rgba(0,0,0,0.45)]">
        <AuthVisual />

        <div className="flex items-center justify-center px-4 py-16 lg:bg-[--background] lg:px-12 lg:py-0">
          <motion.div
            className="w-full max-w-sm"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <Card className="lg:border-none lg:bg-transparent lg:shadow-none lg:ring-0 lg:backdrop-blur-none">
              <CardHeader>
                <CardTitle className="font-heading text-xl">
                  {mode === "signin" ? "Sign in" : "Create an account"}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleSubmit} className="flex flex-col gap-3">
                  <Input
                    type="email"
                    required
                    placeholder="Email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                  />
                  <Input
                    type="password"
                    required
                    minLength={6}
                    placeholder="Password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                  {error && <p className="text-sm text-destructive">{error}</p>}
                  {info && <p className="text-sm text-[--aurora-from]">{info}</p>}
                  <Button type="submit" disabled={loading} className="bg-aurora text-white hover:opacity-90">
                    {loading ? "Working…" : mode === "signin" ? "Sign in" : "Sign up"}
                  </Button>
                </form>
                <button
                  className="mt-4 flex min-h-11 items-center text-sm text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
                  onClick={() => setMode(mode === "signin" ? "signup" : "signin")}
                >
                  {mode === "signin" ? "Need an account? Sign up" : "Already have an account? Sign in"}
                </button>
              </CardContent>
            </Card>
          </motion.div>
        </div>
      </div>
    </div>
  );
}
