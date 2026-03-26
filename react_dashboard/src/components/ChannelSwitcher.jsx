import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
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
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import ExpandLessIcon from "@mui/icons-material/ExpandLess";
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
  const [open, setOpen] = useState(false);
  const [tokenInventory, setTokenInventory] = useState([]);
  const [visibilityReady, setVisibilityReady] = useState(false);
  const [pendingValues, setPendingValues] = useState({});
  const [stickyHiddenValues, setStickyHiddenValues] = useState([]);
  const [orderedValues, setOrderedValues] = useState([]);
  const listboxRef = useRef(null);
  const restoreScrollTopRef = useRef(null);
  const restoreFramesRef = useRef(0);
  const restoreTimeoutRef = useRef(null);

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
    () => new Map(tokenInventory.map((item) => [item.value, item])),
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
      if (knownValues.has(item.value)) return;
      const rawOption = {
        value: item.value,
        label: item.label,
        avatar: item.avatar,
      };
      const hidden =
        Object.prototype.hasOwnProperty.call(pendingValues, item.value)
          ? pendingValues[item.value]
          : !!item.hidden;
      base.push({
        raw: rawOption,
        value: item.value,
        label: item.label,
        avatar: item.avatar,
        meta: getOptionMeta(rawOption),
        tokenName: item.tokenName,
        hidden,
      });
    });

    return base;
  }, [getOptionMeta, inventoryByValue, normalizedOptions, pendingValues, tokenInventory]);

  const selectedOption = useMemo(
    () => mergedOptions.find((option) => option.value === String(value || "")) || null,
    [mergedOptions, value]
  );

  const hiddenOptions = useMemo(
    () => mergedOptions.filter((option) => option.hidden),
    [mergedOptions]
  );

  const buildOrderedValues = (items, currentOrder = []) => {
    const currentIndex = new Map(
      (Array.isArray(currentOrder) ? currentOrder : []).map((value, index) => [value, index])
    );
    const ordered = [...(Array.isArray(items) ? items : [])].sort((a, b) => {
      const hiddenDiff = Number(!!a.hidden) - Number(!!b.hidden);
      if (hiddenDiff !== 0) return hiddenDiff;
      const aIndex = currentIndex.get(a.value);
      const bIndex = currentIndex.get(b.value);
      if (aIndex == null && bIndex == null) return 0;
      if (aIndex == null) return 1;
      if (bIndex == null) return -1;
      return aIndex - bIndex;
    });
    return ordered.map((option) => option.value);
  };

  const groupedOptions = useMemo(
    () => {
      const orderIndex = new Map(
        orderedValues.map((optionValue, index) => [optionValue, index])
      );
      return mergedOptions
        .filter(
          (option) =>
            showHidden || !option.hidden || stickyHiddenValues.includes(option.value)
        )
        .sort((a, b) => {
          const aIndex = orderIndex.get(a.value);
          const bIndex = orderIndex.get(b.value);
          if (aIndex == null && bIndex == null) return 0;
          if (aIndex == null) return 1;
          if (bIndex == null) return -1;
          return aIndex - bIndex;
        })
        .map((option) => ({ ...option }));
    },
    [mergedOptions, orderedValues, showHidden, stickyHiddenValues]
  );

  useEffect(() => {
    setOrderedValues((current) => {
      const next = buildOrderedValues(mergedOptions, current);
      if (
        current.length === next.length &&
        current.every((value, index) => value === next[index])
      ) {
        return current;
      }
      return next;
    });
  }, [mergedOptions]);

  useLayoutEffect(() => {
    if (restoreScrollTopRef.current == null || !listboxRef.current) return;
    const nextScrollTop = restoreScrollTopRef.current;
    listboxRef.current.scrollTop = nextScrollTop;
    let frameId = 0;
    const keepRestoring = () => {
      if (!listboxRef.current || restoreScrollTopRef.current == null) return;
      listboxRef.current.scrollTop = restoreScrollTopRef.current;
      if (restoreFramesRef.current > 0) {
        restoreFramesRef.current -= 1;
        frameId = window.requestAnimationFrame(keepRestoring);
        return;
      }
      restoreScrollTopRef.current = null;
    };
    frameId = window.requestAnimationFrame(keepRestoring);
    return () => {
      window.cancelAnimationFrame(frameId);
      if (restoreTimeoutRef.current) {
        window.clearTimeout(restoreTimeoutRef.current);
        restoreTimeoutRef.current = null;
      }
    };
  }, [groupedOptions, pendingValues, tokenInventory]);

  const prepareScrollRestore = () => {
    restoreScrollTopRef.current = listboxRef.current?.scrollTop ?? null;
    restoreFramesRef.current = 24;
    if (restoreTimeoutRef.current) {
      window.clearTimeout(restoreTimeoutRef.current);
    }
    restoreTimeoutRef.current = window.setTimeout(() => {
      if (listboxRef.current && restoreScrollTopRef.current != null) {
        listboxRef.current.scrollTop = restoreScrollTopRef.current;
      }
      restoreTimeoutRef.current = null;
    }, 250);
  };

  const handleToggleVisibility = async (event, option, nextVisible) => {
    event.preventDefault();
    event.stopPropagation();
    if (!option?.tokenName) return;

    prepareScrollRestore();
    const nextHidden = !nextVisible;
    if (open && nextHidden && !showHidden) {
      setStickyHiddenValues((current) =>
        current.includes(option.value) ? current : [...current, option.value]
      );
    }
    if (!nextHidden) {
      setStickyHiddenValues((current) => current.filter((value) => value !== option.value));
    }
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
      if (nextHidden) {
        setStickyHiddenValues((current) => current.filter((value) => value !== option.value));
      }
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

  const handleToggleShowHidden = () => {
    prepareScrollRestore();
    setShowHidden((current) => !current);
  };

  const renderDropdownPaper = (paperProps) => (
    <Paper {...paperProps}>
      {paperProps.children}
      {visibilityReady && hiddenOptions.length ? (
        <>
          <Divider />
          <Box
            onMouseDown={(event) => {
              event.preventDefault();
              event.stopPropagation();
            }}
            onClick={handleToggleShowHidden}
            sx={{
              px: 1.25,
              py: 0.85,
              display: "flex",
              alignItems: "center",
              gap: 0.5,
              cursor: "pointer",
              "&:hover": { bgcolor: "action.hover" },
            }}
          >
            <Box
              sx={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                width: 24,
                height: 24,
                color: isDark ? "rgba(226,232,240,0.82)" : "rgba(15,23,42,0.6)",
              }}
            >
              {showHidden ? (
                <ExpandLessIcon fontSize="small" />
              ) : (
                <ExpandMoreIcon fontSize="small" />
              )}
            </Box>
            <Typography
              variant="body2"
              sx={{
                color: "text.secondary",
                fontSize: 13,
                fontWeight: 700,
              }}
            >
              {showHidden ? "Hide hidden" : `Show hidden (${hiddenOptions.length})`}
            </Typography>
          </Box>
        </>
      ) : null}
    </Paper>
  );

  return (
    <Box sx={sx || CHANNEL_SWITCHER_SX}>
      <Autocomplete
        open={open}
        size={size}
        options={groupedOptions}
        value={selectedOption}
        disabled={disabled}
        noOptionsText={noOptionsText}
        clearIcon={null}
        ListboxProps={{
          ref: listboxRef,
        }}
        getOptionLabel={(option) => option?.label || ""}
        isOptionEqualToValue={(option, current) => option?.value === current?.value}
        PaperComponent={renderDropdownPaper}
        onOpen={() => setOpen(true)}
        onClose={() => {
          setOpen(false);
          setOrderedValues((current) => buildOrderedValues(mergedOptions, current));
          setStickyHiddenValues([]);
        }}
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
            }}
          >
            {option.tokenName ? (
              <Checkbox
                checked={!option.hidden}
                size="medium"
                sx={{
                  ml: -0.5,
                  mr: 0,
                  p: 0.75,
                  color: isDark ? "rgba(226,232,240,0.82)" : "rgba(15,23,42,0.48)",
                  "&.Mui-checked": {
                    color: isDark ? "#7dd3fc" : "#1976d2",
                  },
                  "&.Mui-disabled": {
                    color: isDark ? "rgba(148,163,184,0.45)" : "rgba(148,163,184,0.75)",
                  },
                  "& .MuiSvgIcon-root": {
                    fontSize: 22,
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
            <Avatar
              src={option.avatar}
              alt={option.label}
              sx={{
                width: 30,
                height: 30,
                opacity: option.hidden ? 0.58 : 1,
              }}
            />
            <Box
              sx={{
                minWidth: 0,
                flex: 1,
              }}
            >
              <Typography
                variant="body2"
                sx={{
                  fontWeight: 700,
                  color: option.hidden ? "text.secondary" : "text.primary",
                  opacity: option.hidden ? 0.82 : 1,
                }}
                noWrap
              >
                {option.label}
              </Typography>
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
                  color: option.hidden ? "text.secondary" : "success.main",
                  bgcolor: option.hidden ? "action.hover" : "rgba(46, 125, 50, 0.12)",
                  border: "1px solid",
                  borderColor: option.hidden ? "divider" : "rgba(46, 125, 50, 0.2)",
                  opacity: option.hidden ? 0.78 : 1,
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
