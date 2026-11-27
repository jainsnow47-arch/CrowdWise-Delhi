import { useEffect, useId, useRef, useState } from "react";
import { searchStops } from "../api";
import type { StopHub } from "../types";

interface StopAutocompleteProps {
  id: string;
  name: string;
  label: string;
  value: string;
  placeholder: string;
  errorText?: string;
  onChange: (hubName: string) => void;
}

export function StopAutocomplete({
  id,
  name,
  label,
  value,
  placeholder,
  errorText,
  onChange,
}: StopAutocompleteProps) {
  const listboxId = useId();
  const hintId = useId();
  const errId = useId();
  const containerRef = useRef<HTMLDivElement>(null);

  const [suggestions, setSuggestions] = useState<StopHub[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const trimmed = value.trim();
    if (trimmed.length < 2) {
      setSuggestions([]);
      setIsOpen(false);
      setActiveIndex(-1);
      return;
    }

    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      setLoading(true);
      try {
        const stops = await searchStops(trimmed, controller.signal);
        setSuggestions(stops);
        const exactOnly =
          stops.length === 1 &&
          stops[0].hub_name.toLowerCase() === trimmed.toLowerCase();
        setIsOpen(stops.length > 0 && !exactOnly);
        setActiveIndex(-1);
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          setSuggestions([]);
        }
      } finally {
        setLoading(false);
      }
    }, 180);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [value]);

  useEffect(() => {
    function handleOutside(event: MouseEvent) {
      if (!containerRef.current?.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleOutside);
    return () => document.removeEventListener("mousedown", handleOutside);
  }, []);

  function selectHub(hub: StopHub) {
    onChange(hub.hub_name);
    setIsOpen(false);
    setActiveIndex(-1);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.nativeEvent.isComposing) return;
    if (!isOpen || suggestions.length === 0) {
      if (e.key === "ArrowDown" && suggestions.length > 0) {
        setIsOpen(true);
        setActiveIndex(0);
        e.preventDefault();
      }
      return;
    }

    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((prev) => (prev + 1) % suggestions.length);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((prev) =>
        prev <= 0 ? suggestions.length - 1 : prev - 1
      );
    } else if (e.key === "Enter" && activeIndex >= 0) {
      e.preventDefault();
      selectHub(suggestions[activeIndex]);
    } else if (e.key === "Escape") {
      setIsOpen(false);
      setActiveIndex(-1);
    }
  }

  const activeOptionId =
    activeIndex >= 0 ? `${listboxId}-opt-${activeIndex}` : undefined;
  const describedBy = errorText ? `${hintId} ${errId}` : hintId;

  return (
    <div className="field" ref={containerRef}>
      <label className="field-label" htmlFor={id}>
        {label}
      </label>
      <span id={hintId} className="field-hint">
        Type at least 2 characters to search stop hubs ({placeholder}).
      </span>
      <div className="combobox-wrap">
        <input
          id={id}
          name={name}
          type="text"
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={isOpen}
          aria-controls={listboxId}
          aria-activedescendant={activeOptionId}
          aria-describedby={describedBy}
          aria-invalid={errorText ? "true" : undefined}
          autoComplete="off"
          autoCorrect="off"
          autoCapitalize="none"
          spellCheck={false}
          required
          value={value}
          placeholder={placeholder}
          className="text-input combobox-input"
          onChange={(e) => {
            onChange(e.target.value);
          }}
          onFocus={() => {
            if (suggestions.length > 0) setIsOpen(true);
          }}
          onKeyDown={handleKeyDown}
        />
        {value.length > 0 && (
          <button
            type="button"
            className="combobox-clear"
            aria-label={`Clear ${label}`}
            onClick={() => {
              onChange("");
              setSuggestions([]);
              setIsOpen(false);
            }}
          >
            ×
          </button>
        )}

        {isOpen && (
          <ul id={listboxId} role="listbox" aria-label={`${label} suggestions`} className="listbox">
            {suggestions.map((hub, idx) => {
              const isActive = idx === activeIndex;
              return (
                <li
                  key={hub.hub_name}
                  id={`${listboxId}-opt-${idx}`}
                  role="option"
                  aria-selected={isActive}
                  className={`listbox-option${isActive ? " is-active" : ""}`}
                  onMouseDown={(e) => {
                    e.preventDefault();
                    selectHub(hub);
                  }}
                >
                  <span>{hub.hub_name}</span>
                  <span className="listbox-meta">
                    {hub.stop_ids.length} {hub.stop_ids.length === 1 ? "stop" : "stops"}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </div>
      {loading && (
        <span className="field-hint" aria-hidden="true">
          Searching stops…
        </span>
      )}
      {errorText && (
        <span id={errId} className="field-hint" style={{ color: "var(--tier-crowded-fg)" }}>
          {errorText}
        </span>
      )}
    </div>
  );
}
