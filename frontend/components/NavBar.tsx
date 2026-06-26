"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Compass, LogOut, MapPinned, Plane } from "lucide-react";
import { useAuth } from "@/components/AuthProvider";
import { Button } from "@/components/ui/button";

export function NavBar() {
  const { session, signOut } = useAuth();
  const router = useRouter();

  async function handleSignOut() {
    await signOut();
    router.push("/");
  }

  return (
    <header className="glass sticky top-0 z-20 flex items-center justify-between gap-2 px-4 py-3 sm:px-6">
      <Link href="/" className="font-heading flex items-center gap-2 text-base font-medium sm:text-lg">
        <Compass className="size-5 shrink-0 text-[--aurora-to]" strokeWidth={1.75} />
        <span className="hidden sm:inline">Wayfare</span>
      </Link>
      <nav className="flex items-center gap-1 text-sm sm:gap-2">
        {session ? (
          <>
            <Button asChild variant="ghost" size="sm" className="min-h-11 min-w-11 sm:min-h-0 sm:min-w-0">
              <Link href="/plan" aria-label="Plan a trip">
                <Plane className="size-4 sm:hidden" />
                <span className="hidden sm:inline">Plan a trip</span>
              </Link>
            </Button>
            <Button asChild variant="ghost" size="sm" className="min-h-11 min-w-11 sm:min-h-0 sm:min-w-0">
              <Link href="/trips" aria-label="My trips">
                <MapPinned className="size-4 sm:hidden" />
                <span className="hidden sm:inline">My trips</span>
              </Link>
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleSignOut}
              aria-label="Sign out"
              className="min-h-11 min-w-11 sm:min-h-0 sm:min-w-0"
            >
              <LogOut className="size-4 sm:hidden" />
              <span className="hidden sm:inline">Sign out</span>
            </Button>
          </>
        ) : (
          <Button asChild size="sm" className="min-h-11 sm:min-h-0">
            <Link href="/login">Sign in</Link>
          </Button>
        )}
      </nav>
    </header>
  );
}
