import { useEffect, useMemo, useState } from "react";
import { Autocomplete, Avatar, Box, TextField, Typography } from "@mui/material";
import YouTubeIcon from "@mui/icons-material/YouTube";

const loadRecentChannels = (storageKey) => {
  if (!storageKey || typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(storageKey);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed.map(String).filter(Boolean) : [];
  } catch {
    return [];
  }
};

const saveRecentChannels = (storageKey, items) => {
  if (!storageKey || typeof window === "undefined") return;
  try {
    window.localStorage.setItem(
      storageKey,
      JSON.stringify(Array.from(new Set((items || []).map(String).filter(Boolean))).slice(0, 5))
    );
  } catch {
    // Ignore localStorage errors and keep the switcher functional.
  }
};

const defaultGetValue = (option) => String(option?.value ?? "");
const defaultGetLabel = (option) => String(option?.label ?? option?.value ?? "");
const defaultGetAvatar = (option) => option?.avatar || "";
const defaultGetMeta = () => "";

const ChannelSwitcher = ({
  options,
  value,
  onChange,
  label = "Channel",
  placeholder = "Search by channel name",
  sx,
  size = "small",
  recentStorageKey,
  noOptionsText = "No channels found",
  getOptionValue = defaultGetValue,
  getOptionLabel = defaultGetLabel,
  getOptionAvatar = defaultGetAvatar,
  getOptionMeta = defaultGetMeta,
}) => {
  const [recentChannels, setRecentChannels] = useState(() => loadRecentChannels(recentStorageKey));

  const normalizedOptions = useMemo(
    () =>
      (options || []).map((option) => ({
        raw: option,
        value: getOptionValue(option),
        label: getOptionLabel(option),
        avatar: getOptionAvatar(option),
        meta: getOptionMeta(option),
      })),
    [options, getOptionAvatar, getOptionLabel, getOptionMeta, getOptionValue]
  );

  const selectedOption = useMemo(
    () => normalizedOptions.find((option) => option.value === String(value || "")) || null,
    [normalizedOptions, value]
  );

  useEffect(() => {
    if (!recentStorageKey || !value) return;
    setRecentChannels((current) => {
      const next = [String(value), ...current.filter((item) => item !== String(value))].slice(0, 5);
      saveRecentChannels(recentStorageKey, next);
      return next;
    });
  }, [recentStorageKey, value]);

  const groupedOptions = useMemo(() => {
    if (!recentStorageKey) return normalizedOptions;
    const recentRank = new Map(recentChannels.map((item, index) => [item, index]));
    const recent = [];
    const others = [];

    normalizedOptions.forEach((option) => {
      if (recentRank.has(option.value)) {
        recent.push({ ...option, group: "Recent" });
      } else {
        others.push({ ...option, group: "All channels" });
      }
    });

    recent.sort((a, b) => recentRank.get(a.value) - recentRank.get(b.value));
    return [...recent, ...others];
  }, [normalizedOptions, recentChannels, recentStorageKey]);

  return (
    <Box sx={sx}>
      <Autocomplete
        size={size}
        options={groupedOptions}
        value={selectedOption}
        noOptionsText={noOptionsText}
        getOptionLabel={(option) => option?.label || ""}
        groupBy={recentStorageKey ? (option) => option.group || "All channels" : undefined}
        isOptionEqualToValue={(option, current) => option?.value === current?.value}
        filterOptions={(items, state) => {
          const query = state.inputValue.trim().toLowerCase();
          if (!query) return items;
          return items.filter((option) =>
            [option.label, option.value, option.meta]
              .filter(Boolean)
              .join(" ")
              .toLowerCase()
              .includes(query)
          );
        }}
        onChange={(_, nextValue) => onChange?.(nextValue?.raw || null)}
        renderInput={(params) => (
          <TextField
            {...params}
            label={label}
            placeholder={placeholder}
            InputProps={{
              ...params.InputProps,
              startAdornment: (
                <>
                  {selectedOption?.avatar ? (
                    <Avatar
                      src={selectedOption.avatar}
                      alt={selectedOption.label}
                      sx={{ width: 22, height: 22, mr: 1 }}
                    />
                  ) : (
                    <YouTubeIcon sx={{ fontSize: 18, color: "text.secondary", mr: 1 }} />
                  )}
                  {params.InputProps.startAdornment}
                </>
              ),
            }}
          />
        )}
        renderOption={(props, option) => (
          <Box component="li" {...props} sx={{ display: "flex", alignItems: "center", gap: 1.25, py: 1 }}>
            <Avatar src={option.avatar} alt={option.label} sx={{ width: 30, height: 30 }} />
            <Box sx={{ minWidth: 0, flex: 1 }}>
              <Typography variant="body2" sx={{ fontWeight: 700 }} noWrap>
                {option.label}
              </Typography>
              {option.meta ? (
                <Typography variant="caption" color="text.secondary" noWrap sx={{ display: "block" }}>
                  {option.meta}
                </Typography>
              ) : null}
            </Box>
          </Box>
        )}
      />
    </Box>
  );
};

export default ChannelSwitcher;
