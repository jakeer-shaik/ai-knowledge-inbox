import { useCallback, useRef, useState } from "react";

/**
 * Blur-first field validation:
 *  - no error while typing in a fresh field
 *  - validate when a field the user has typed in is left (blur), or on submit
 *  - leaving a field that was never typed in shows nothing (e.g. an auto-focused box)
 *  - an existing error clears on the first corrective keystroke
 */
export function useField(initialValue, validate) {
  const [value, setValue] = useState(initialValue);
  const [error, setError] = useState(null);
  const edited = useRef(false);

  const onChange = useCallback((event) => {
    edited.current = true;
    setValue(event.target.value);
    setError(null);
  }, []);

  const onBlur = useCallback(() => {
    if (edited.current) setError(validate(value));
  }, [validate, value]);

  /** Validate now (on submit). Returns the error message, or null when valid. */
  const validateNow = useCallback(() => {
    const message = validate(value);
    setError(message);
    return message;
  }, [validate, value]);

  const reset = useCallback(() => {
    edited.current = false;
    setValue(initialValue);
    setError(null);
  }, [initialValue]);

  return {
    value,
    error,
    setError,
    validateNow,
    reset,
    inputProps: { value, onChange, onBlur, "aria-invalid": error ? true : undefined },
  };
}
