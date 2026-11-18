import { useEffect, useState } from "react";
import { api } from "../api";

/** One-off backend health check, used for the connection indicator in the header. */
export function useHealth() {
  const [health, setHealth] = useState({ status: "checking", data: null });

  useEffect(() => {
    let cancelled = false;
    api
      .health()
      .then((data) => !cancelled && setHealth({ status: "online", data }))
      .catch(() => !cancelled && setHealth({ status: "offline", data: null }));
    return () => {
      cancelled = true;
    };
  }, []);

  return health;
}
