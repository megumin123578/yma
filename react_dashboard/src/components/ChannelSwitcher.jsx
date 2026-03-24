import { useEffect, useMemo, useState } from "react";
import {
  Autocomplete,
  Avatar,
  Box,
  Checkbox,
  CircularProgress,
  Divider,
  Paper,
  TextField,
  Typography,
  useTheme,
} from "@mui/material";
import YouTubeIcon from "@mui/icons-material/YouTube";
import { listTokens, setTokenVisibility } from "../services/userService";

export const CHANNEL_SWITCHER_SX = {
  minWidth: { xs: "100%", sm: 270 },
  flex: "0 1 312px",
  maxWidth: 356,
};

const defaultGetValue = (option) => String(option?.value ?? "");
const defaultGetLabel = (option) => String(option?.label ?? option?.value ?? "");
const defaultGetAvatar = (option) => option?.avatar || "";
const defaultGetMeta = () => "";
const normalizeTokenValue = (value) => String(value || "").replace(/\.pickle$/i, "").trim();

let tokenInventoryCache = null;
let tokenInventoryPromise = null;

const loadTokenInventory = async () => {
  if (tokenInventoryCache) return tokenInventoryCache;
  if (tokenInventoryPromise) return tokenInventoryPromise;

  tokenInventoryPromise = listTokens()
    .then((data) => {
      const items = Array.isArray(data?.tokens) ? data.tokens : [];
      tokenInventoryCache = items
        .map((item) => {
          const tokenName = String(item?.name || "").trim();
          const value = normalizeTokenValue(tokenName);
          if (!value) return null;
          return {
            tokenName,
            value,
            label: String(item?.label || value),
            avatar: item?.avatar || "",
            hidden: !!item?.hidden,
            owned: item?.owned !== false,
          };
        })
        .filter(Boolean);
      return tokenInventoryCache;
    })
    .catch(() => {
      tokenInventoryCache = [];
      return tokenInventoryCache;
    })
    .finally(() => {
      tokenInventoryPromise = null;
    });

  return tokenInventoryPromise;
};

const ChannelSwitcher = ({
  options,
  value,
  onChange,
  label = "Channel",
  placeholder = "Search by channel name",
  sx,
  size = "small",
  disabled = false,
  noOptionsText = "No channels found",
  getOptionValue = defaultGetValue,
  getOptionLabel = defaultGetLabel,
  getOptionAvatar = defaultGetAvatar,
  getOptionMeta = defaultGetMeta,
}) => {
  const theme = useTheme();
  const isDark = theme.palette.mode === "dark";
  const [showHidden, setShowHidden] = useState(false);
  const [tokenInventory, setTokenInventory] = useState([]);
  const [visibilityReady, setVisibilityReady] = useState(false);
  const [pendingValues, setPendingValues] = useState({});

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

  useEffect(() => {
    let active = true;
    loadTokenInventory().then((items) => {
      if (!active) return;
      setTokenInventory(items);
      setVisibilityReady(true);
    });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    const handleVisibilityChanged = (event) => {
      const nextValue = normalizeTokenValue(event?.detail?.value);
      if (!nextValue) return;
      setTokenInventory((current) =>
        current.map((item) =>
          item.value === nextValue ? { ...item, hidden: !!event?.detail?.hidden } : item
        )
      );
    };
    window.addEventListener("token-visibility-changed", handleVisibilityChanged);
    return () => window.removeEventListener("token-visibility-changed", handleVisibilityChanged);
  }, []);

  const inventoryByValue = useMemo(
    () => new Map(tokenInventory.filter((item) => item.owned).map((item) => [item.value, item])),
    [tokenInventory]
  );

  const mergedOptions = useMemo(() => {
    const base = normalizedOptions.map((option) => {
      const inventory = inventoryByValue.get(option.value);
      const hidden =
        Object.prototype.hasOwnProperty.call(pendingValues, option.value)
          ? pendingValues[option.value]
          : !!inventory?.hidden;
      return {
        ...option,
        tokenName: inventory?.tokenName || "",
        hidden,
      };
    });

    const knownValues = new Set(base.map((option) => option.value));
    tokenInventory.forEach((item) => {
      if (!item.owned || knownValues.has(item.value)) return;
      const hidden =
        Object.prototype.hasOwnProperty.call(pendingValues, item.value)
          ? pendingValues[item.value]
          : !!item.hidden;
      base.push({
        raw: { value: item.value, label: item.label, avatar: item.avatar },
        value: item.value,
        label: item.label,
        avatar: item.avatar,
        meta: "",
        tokenName: item.tokenName,
        hidden,
      });
    });

    return base;
  }, [inventoryByValue, normalizedOptions, pendingValues, tokenInventory]);

  const selectedOption = useMemo(
    () => mergedOptions.find((option) => option.value === String(value || "")) || null,
    [mergedOptions, value]
  );

  const hiddenOptions = useMemo(
    () => mergedOptions.filter((option) => option.hidden),
    [mergedOptions]
  );

  const visibleOptions = useMemo(
    () => mergedOptions.filter((option) => !option.hidden),
    [mergedOptions]
  );

  const groupedOptions = useMemo(() => {
    const visible = visibleOptions.map((option) => ({ ...option, group: "Channels" }));
    const hidden = showHidden
      ? hiddenOptions.map((option) => ({ ...option, group: "Hidden" }))
      : [];
    return [...visible, ...hidden];
  }, [hiddenOptions, showHidden, visibleOptions]);

  const handleToggleVisibility = async (event, option, nextVisible) => {
    event.preventDefault();
    event.stopPropagation();
    if (!option?.tokenName) return;

    const nextHidden = !nextVisible;
    setPendingValues((current) => ({
      ...current,
      [option.value]: nextHidden,
      [`${option.value}:saving`]: true,
    }));

    try {
      await setTokenVisibility(option.tokenName, nextHidden);
      setTokenInventory((current) =>
        current.map((item) =>
          item.value === option.value ? { ...item, hidden: nextHidden } : item
        )
      );
      if (typeof window !== "undefined") {
        window.dispatchEvent(
          new CustomEvent("token-visibility-changed", {
            detail: { value: option.value, hidden: nextHidden },
          })
        );
      }
    } catch {
      setPendingValues((current) => {
        const next = { ...current };
        delete next[option.value];
        return next;
      });
    } finally {
      setPendingValues((current) => {
        const next = { ...current };
        delete next[option.value];
        delete next[`${option.value}:saving`];
        return next;
      });
    }
  };

  const renderDropdownPaper = (paperProps) => (
    <Paper {...paperProps}>
      {paperProps.children}
      {visibilityReady && hiddenOptions.length ? (
        <>
          <Divider />
          <Box
            onMouseDown={(event) => event.preventDefault()}
            onClick={() => setShowHidden((current) => !current)}
            sx={{
              px: 1.5,
              py: 1.25,
              cursor: "pointer",
              color: "text.secondary",
              fontSize: 13,
              fontWeight: 700,
              "&:hover": { bgcolor: "action.hover" },
            }}
          >
            {showHidden ? "Hide hidden" : `Show hidden (${hiddenOptions.length})`}
          </Box>
        </>
      ) : null}
    </Paper>
  );

  return (
    <Box sx={sx || CHANNEL_SWITCHER_SX}>
      <Autocomplete
        size={size}
        options={groupedOptions}
        value={selectedOption}
        disabled={disabled}
        noOptionsText={noOptionsText}
        clearIcon={null}
        getOptionLabel={(option) => option?.label || ""}
        groupBy={(option) => option.group || "Channels"}
        isOptionEqualToValue={(option, current) => option?.value === current?.value}
        PaperComponent={renderDropdownPaper}
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
                      sx={{ width: 22, height: 22, mr: 0.5 }}
                    />
                  ) : (
                    <YouTubeIcon sx={{ fontSize: 18, color: "text.secondary", mr: 0.5 }} />
                  )}
                  {params.InputProps.startAdornment}
                </>
              ),
              endAdornment: (
                <>
                  {selectedOption?.meta ? (
                    <Box
                      sx={{
                        mr: 0.25,
                        px: 0.5,
                        py: 0.15,
                        borderRadius: 999,
                        fontSize: 11,
                        fontWeight: 800,
                        lineHeight: 1,
                        color: "success.main",
                        bgcolor: "rgba(46, 125, 50, 0.12)",
                        border: "1px solid",
                        borderColor: "rgba(46, 125, 50, 0.2)",
                      }}
                    >
                      {selectedOption.meta}
                    </Box>
                  ) : null}
                  <Box sx={{ ml: -0.5 }}>{params.InputProps.endAdornment}</Box>
                </>
              ),
            }}
          />
        )}
        renderOption={(props, option) => (
          <Box
            component="li"
            {...props}
            sx={{
              display: "flex",
              alignItems: "center",
              gap: 0.75,
              py: 1,
              pl: 0.5,
              opacity: option.hidden ? 0.72 : 1,
            }}
          >
            {option.tokenName ? (
              <Checkbox
                checked={!option.hidden}
                size="small"
                sx={{
                  ml: -0.5,
                  mr: 0,
                  p: 0.5,
                  color: isDark ? "rgba(226,232,240,0.82)" : "rgba(15,23,42,0.48)",
                  "&.Mui-checked": {
                    color: isDark ? "#7dd3fc" : "#1976d2",
                  },
                  "&.Mui-disabled": {
                    color: isDark ? "rgba(148,163,184,0.45)" : "rgba(148,163,184,0.75)",
                  },
                  "& .MuiSvgIcon-root": {
                    filter: isDark ? "drop-shadow(0 0 4px rgba(125,211,252,0.18))" : "none",
                  },
                }}
                onMouseDown={(event) => {
                  event.preventDefault();
                  event.stopPropagation();
                }}
                onClick={(event) => handleToggleVisibility(event, option, option.hidden)}
                disabled={!!pendingValues[`${option.value}:saving`]}
              />
            ) : (
              <Box sx={{ width: 30 }} />
            )}
            <Avatar src={option.avatar} alt={option.label} sx={{ width: 30, height: 30 }} />
            <Box sx={{ minWidth: 0, flex: 1 }}>
              <Typography variant="body2" sx={{ fontWeight: 700 }} noWrap>
                {option.label}
              </Typography>
              {option.hidden ? (
                <Typography variant="caption" sx={{ color: "text.secondary" }}>
                  Hidden
                </Typography>
              ) : null}
            </Box>
            {pendingValues[`${option.value}:saving`] ? (
              <CircularProgress size={14} sx={{ mr: 0.5 }} />
            ) : null}
            {option.meta ? (
              <Box
                sx={{
                  minWidth: 20,
                  px: 0.75,
                  py: 0.25,
                  borderRadius: 999,
                  fontSize: 12,
                  fontWeight: 800,
                  lineHeight: 1,
                  color: "success.main",
                  bgcolor: "rgba(46, 125, 50, 0.12)",
                  border: "1px solid",
                  borderColor: "rgba(46, 125, 50, 0.2)",
                }}
              >
                {option.meta}
              </Box>
            ) : null}
          </Box>
        )}
      />
    </Box>
  );
};

export default ChannelSwitcher;
