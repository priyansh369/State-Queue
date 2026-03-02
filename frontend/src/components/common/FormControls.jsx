import { useState } from "react";

export function TextInput({ label, value, onChange, type = "text", ...rest }) {
  const [show, setShow] = useState(false);
  const isPassword = type === "password";

  return (
    <div className="form-group password-field">
      <label>{label}</label>
      <div className="input-with-toggle">
        <input
          type={isPassword ? (show ? "text" : "password") : type}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          {...rest}
        />
        {isPassword && (
          <button
            type="button"
            className="show-hide-btn"
            onClick={() => setShow((prev) => !prev)}
          >
            {show ? "Hide" : "Show"}
          </button>
        )}
      </div>
    </div>
  );
}

export function Select({ label, value, onChange, options, ...rest }) {
  return (
    <div className="form-group">
      <label>{label}</label>
      <select value={value} onChange={(e) => onChange(e.target.value)} {...rest}>
        {options.map((opt) => (
          <option key={opt.value} value={opt.value} disabled={Boolean(opt.disabled)}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );
}

