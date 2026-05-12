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
import ChevronRightIcon from "@mui/icons-material/ChevronRight";
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
const normalizeTokenValue = (value) => String(value || "").trim();
const normalizeHierarchyName = (value) => String(value || "").trim();
const isOptionHidden = (option) => !!option?.hidden;
const CREDENTIALS_CHANGED_EVENT = "credentials-data-changed";
const SUBMENU_VIEWPORT_PADDING = 12;
const SUBMENU_GAP = 4;
const SUBMENU_TOP_OFFSET = -10;
const compareMenuLabels = (left, right) =>
  String(left || "").localeCompare(String(right || ""), undefined, {
    sensitivity: "base",
    numeric: true,
  });
const sortOptionsByVisibility = (items) =>
  [...(Array.isArray(items) ? items : [])]
    .sort((a, b) => {
      const hiddenDiff = Number(isOptionHidden(a)) - Number(isOptionHidden(b));
      if (hiddenDiff !== 0) return hiddenDiff;
      return compareMenuLabels(a?.label || a?.value, b?.label || b?.value);
    });
const getAnchorRect = (element) => {
  if (!element || typeof element.getBoundingClientRect !== "function") return null;
  const rect = element.getBoundingClientRect();
  if (!rect || (!rect.width && !rect.height)) return null;
  return rect;
};
const getSubmenuLayerSx = (rect, width, zIndex) => {
  if (!rect) return { display: "none" };
  const viewportWidth =
    typeof window !== "undefined" ? window.innerWidth : rect.right + width + SUBMENU_VIEWPORT_PADDING;
  const viewportHeight =
    typeof window !== "undefined" ? window.innerHeight : rect.bottom + 360 + SUBMENU_VIEWPORT_PADDING;
  const maxLeft = Math.max(SUBMENU_VIEWPORT_PADDING, viewportWidth - width - SUBMENU_VIEWPORT_PADDING);
  const left = Math.max(
    SUBMENU_VIEWPORT_PADDING,
    Math.min(rect.right + SUBMENU_GAP, maxLeft)
  );
  const maxTop = Math.max(SUBMENU_VIEWPORT_PADDING, viewportHeight - 360 - SUBMENU_VIEWPORT_PADDING);
  const top = Math.max(
    SUBMENU_VIEWPORT_PADDING,
    Math.min(rect.top + SUBMENU_TOP_OFFSET, maxTop)
  );
  return {
    position: "fixed",
    top,
    left,
    zIndex,
  };
};

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
            project_name: normalizeHierarchyName(item?.project_name),
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
  showAllLabel = "Show all",
  showAllSelectedLabel = "All channels",
  showAllDisabled = true,
  showAllVisible = true,
  showAllActive = false,
  onShowAllClick,
  textFieldSx,
}) => {
  const theme = useTheme();
  const isDark = theme.palette.mode === "dark";
  const [showHidden, setShowHidden] = useState(false);
  const [open, setOpen] = useState(false);
  const [inputValue, setInputValue] = useState("");
  const [tokenInventory, setTokenInventory] = useState([]);
  const [visibilityReady, setVisibilityReady] = useState(false);
  const [pendingValues, setPendingValues] = useState({});
  const [stickyHiddenValues, setStickyHiddenValues] = useState([]);
  const [hoveredProjectKey, setHoveredProjectKey] = useState("");
  const [hoveredProjectRect, setHoveredProjectRect] = useState(null);
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
        project_name: normalizeHierarchyName(option?.project_name),
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

  useEffect(() => {
    let active = true;
    const reloadInventory = () => {
      tokenInventoryCache = null;
      tokenInventoryPromise = null;
      loadTokenInventory().then((items) => {
        if (!active) return;
        setTokenInventory(items);
        setVisibilityReady(true);
      });
    };
    window.addEventListener(CREDENTIALS_CHANGED_EVENT, reloadInventory);
    return () => {
      active = false;
      window.removeEventListener(CREDENTIALS_CHANGED_EVENT, reloadInventory);
    };
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
        project_name: option.project_name || inventory?.project_name || "",
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
        project_name: item.project_name || "",
      });
    });

    return base;
  }, [getOptionMeta, inventoryByValue, normalizedOptions, pendingValues, tokenInventory]);

  const selectedValue = String(value || "");

  const hiddenOptions = useMemo(
    () => mergedOptions.filter((option) => isOptionHidden(option)),
    [mergedOptions]
  );

  const sortedOptions = useMemo(() => sortOptionsByVisibility(mergedOptions), [mergedOptions]);

  const groupedOptions = useMemo(
    () => {
      return sortedOptions
        .filter(
          (option) =>
            showHidden ||
            !isOptionHidden(option) ||
            stickyHiddenValues.includes(option.value) ||
            option.value === selectedValue
        )
        .map((option) => ({ ...option }));
    },
    [selectedValue, showHidden, sortedOptions, stickyHiddenValues]
  );

  const hierarchyMenu = useMemo(() => {
    const projectsMap = new Map();
    const ungroupedChannels = [];

    groupedOptions.forEach((option) => {
      const projectName = normalizeHierarchyName(option.project_name);
      if (!projectName) {
        ungroupedChannels.push(option);
        return;
      }
      let projectEntry = projectsMap.get(projectName);
      if (!projectEntry) {
        projectEntry = {
          key: `project:${projectName}`,
          type: "project",
          label: projectName,
          projectName,
          items: [],
        };
        projectsMap.set(projectName, projectEntry);
      }
      projectEntry.items.push(option);
    });

    const projects = Array.from(projectsMap.values())
      .map((entry) => ({
        ...entry,
        items: sortOptionsByVisibility(entry.items),
      }))
      .sort((a, b) => compareMenuLabels(a.label, b.label));

    return {
      projects,
      ungroupedChannels: sortOptionsByVisibility(ungroupedChannels),
      hasHierarchy: projects.length > 0,
    };
  }, [groupedOptions]);

  const topLevelHierarchyEntries = hierarchyMenu.projects;

  const rootChannelOptions = useMemo(
    () =>
      groupedOptions.filter(
        (option) => !normalizeHierarchyName(option.project_name)
      ),
    [groupedOptions]
  );

  const selectedOption = useMemo(
    () =>
      groupedOptions.find((option) => option.value === selectedValue) ||
      mergedOptions.find((option) => option.value === selectedValue) ||
      (showAllActive
        ? {
            raw: null,
            value: "__all__",
            label: showAllSelectedLabel,
            avatar: "",
            meta: "",
            hidden: false,
            tokenName: "",
          }
        : null) ||
      null,
    [groupedOptions, mergedOptions, selectedValue, showAllActive, showAllSelectedLabel]
  );

  const normalizedSelectedLabel = String(selectedOption?.label || "").trim().toLowerCase();
  const normalizedSelectedValue = String(selectedOption?.value || "").trim().toLowerCase();
  const normalizedInputQuery = inputValue.trim().toLowerCase();
  const hasTypedQuery =
    !!normalizedInputQuery &&
    normalizedInputQuery !== normalizedSelectedLabel &&
    normalizedInputQuery !== normalizedSelectedValue;
  const showHierarchyMenu = !hasTypedQuery && hierarchyMenu.hasHierarchy;
  const showDropdownFooter =
    hiddenOptions.length > 0 || (showAllVisible && typeof onShowAllClick === "function");

  const selectedHierarchyPath = useMemo(() => {
    for (const projectEntry of topLevelHierarchyEntries) {
      if ((projectEntry.items || []).some((option) => option.value === selectedValue)) {
        return { projectKey: projectEntry.key };
      }
    }
    return { projectKey: "" };
  }, [selectedValue, topLevelHierarchyEntries]);

  useEffect(() => {
    if (!showHierarchyMenu) {
      setHoveredProjectKey("");
      setHoveredProjectRect(null);
    }
  }, [showHierarchyMenu]);

  useEffect(() => {
    if (open) return;
    setInputValue(selectedOption?.label || "");
  }, [open, selectedOption]);

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

  const resetHierarchyHover = () => {
    setHoveredProjectKey("");
    setHoveredProjectRect(null);
  };

  const handleSelectOption = (option) => {
    if (!option) return;
    setInputValue(option.label || "");
    onChange?.(option.raw || null);
    setOpen(false);
    setStickyHiddenValues([]);
    resetHierarchyHover();
  };

  const activeProjectEntry =
    topLevelHierarchyEntries.find((entry) => entry.key === hoveredProjectKey) ||
    null;
  const activeProjectRect = hoveredProjectRect;

  const menuRowSx = {
    px: 1,
    py: 0.8,
    minHeight: 42,
    display: "flex",
    alignItems: "center",
    gap: 1,
    cursor: "pointer",
    borderRadius: 1.5,
  };

  const renderCountPill = (value) => (
    <Box
      sx={{
        minWidth: 22,
        px: 0.65,
        py: 0.2,
        borderRadius: 999,
        fontSize: 11,
        fontWeight: 800,
        lineHeight: 1,
        textAlign: "center",
        color: "text.secondary",
        bgcolor: "action.hover",
        border: "1px solid",
        borderColor: "divider",
        flexShrink: 0,
      }}
    >
      {value}
    </Box>
  );

  const renderMenuLeaf = (option, menuProps = {}) => {
    const { onHover, showPath = false } = menuProps;
    const optionIsHidden = isOptionHidden(option);
    const isSelected = option.value === selectedValue;
    return (
      <Box
        key={option.value}
        onMouseDown={(event) => event.preventDefault()}
        onMouseEnter={() => onHover?.(option)}
        onClick={() => handleSelectOption(option)}
        sx={{
          ...menuRowSx,
          bgcolor: isSelected ? "action.selected" : "transparent",
          "&:hover": {
            bgcolor: isSelected ? "action.selected" : "action.hover",
          },
        }}
      >
        {option.tokenName ? (
          <Checkbox
            checked={!option.hidden}
            size="small"
            sx={{
              ml: -0.25,
              mr: -0.25,
              p: 0.5,
              color: isDark ? "rgba(226,232,240,0.82)" : "rgba(15,23,42,0.48)",
              "&.Mui-checked": {
                color: isDark ? "#7dd3fc" : "#1976d2",
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
          <Box sx={{ width: 28 }} />
        )}
        <Avatar
          src={option.avatar}
          alt={option.label}
          sx={{ width: 28, height: 28, opacity: optionIsHidden ? 0.58 : 1 }}
        />
        <Box sx={{ minWidth: 0, flex: 1 }}>
          <Typography
            variant="body2"
            noWrap
            sx={{
              fontWeight: isSelected ? 800 : 700,
              color: optionIsHidden ? "text.secondary" : "text.primary",
              opacity: optionIsHidden ? 0.82 : 1,
            }}
          >
            {option.label}
          </Typography>
          {showPath && option.project_name && (
            <Typography
              variant="caption"
              noWrap
              sx={{ display: "block", color: "text.secondary", mt: 0.15 }}
            >
              {option.project_name}
            </Typography>
          )}
        </Box>
        {pendingValues[`${option.value}:saving`] ? (
          <CircularProgress size={14} sx={{ mr: 0.25 }} />
        ) : null}
        {option.meta ? (
          <Box
            sx={{
              minWidth: 20,
              px: 0.7,
              py: 0.2,
              borderRadius: 999,
              fontSize: 11,
              fontWeight: 800,
              lineHeight: 1,
              color: optionIsHidden ? "text.secondary" : "success.main",
              bgcolor: optionIsHidden ? "action.hover" : "rgba(46, 125, 50, 0.12)",
              border: "1px solid",
              borderColor: optionIsHidden ? "divider" : "rgba(46, 125, 50, 0.2)",
            }}
          >
            {option.meta}
          </Box>
        ) : null}
      </Box>
    );
  };

  const renderFlyoutPanel = (children, width, panelSx = null) => (
    <Box
      sx={{
        width,
        maxHeight: 360,
        p: 0.75,
        overflowY: "auto",
        border: "1px solid",
        borderColor: "divider",
        borderRadius: 2,
        bgcolor: "background.paper",
        boxShadow: isDark
          ? "0 18px 40px rgba(2, 6, 23, 0.55)"
          : "0 18px 40px rgba(15, 23, 42, 0.14)",
        ...(panelSx || {}),
      }}
    >
      {children}
    </Box>
  );

  const renderHierarchyMenu = () => (
    <Box
      sx={{
        py: 0.75,
        maxHeight: 360,
        overflowY: "auto",
      }}
    >
      {topLevelHierarchyEntries.map((entry) => {
        const isActive = activeProjectEntry?.key === entry.key;
        const channelCount = entry.items?.length || 0;
        return (
          <Box
            key={entry.key}
            onMouseDown={(event) => event.preventDefault()}
            onMouseEnter={(event) => {
              setHoveredProjectKey(entry.key);
              setHoveredProjectRect(getAnchorRect(event.currentTarget));
            }}
            sx={{
              ...menuRowSx,
              justifyContent: "space-between",
              bgcolor: isActive ? "action.selected" : "transparent",
              "&:hover": {
                bgcolor: isActive ? "action.selected" : "action.hover",
              },
            }}
          >
            <Box sx={{ minWidth: 0, flex: 1 }}>
              <Typography variant="body2" noWrap sx={{ fontWeight: 800, lineHeight: 1.3 }}>
                {entry.label}
              </Typography>
            </Box>
            {renderCountPill(channelCount)}
            <ChevronRightIcon
              fontSize="small"
              sx={{ color: "text.secondary", flexShrink: 0 }}
            />
          </Box>
        );
      })}
      {topLevelHierarchyEntries.length && rootChannelOptions.length ? (
        <Divider sx={{ my: 0.75 }} />
      ) : null}
      {rootChannelOptions.map((option) =>
        renderMenuLeaf(option, {
          onHover: resetHierarchyHover,
        })
      )}
    </Box>
  );

  const renderDropdownPaper = (paperProps) => (
    <Paper {...paperProps}>
      {showHierarchyMenu ? renderHierarchyMenu() : paperProps.children}
      {visibilityReady && showDropdownFooter ? (
        <>
          <Divider />
          <Box
            sx={{
              px: 1,
              py: 0.7,
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 1,
            }}
          >
            {hiddenOptions.length ? (
              <Box
                onMouseDown={(event) => {
                  event.preventDefault();
                  event.stopPropagation();
                }}
                onClick={handleToggleShowHidden}
                sx={{
                  px: 0.75,
                  py: 0.45,
                  display: "flex",
                  alignItems: "center",
                  gap: 0.5,
                  cursor: "pointer",
                  borderRadius: 1.5,
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
            ) : (
              <Box sx={{ minWidth: 12, minHeight: 1 }} />
            )}
            {showAllVisible ? (
              <Box
                onMouseDown={(event) => {
                  event.preventDefault();
                  event.stopPropagation();
                }}
                onClick={() => {
                  if (showAllDisabled || typeof onShowAllClick !== "function") return;
                  onShowAllClick();
                  setOpen(false);
                  setStickyHiddenValues([]);
                }}
                sx={{
                  color: showAllActive
                    ? isDark
                      ? "#7dd3fc"
                      : "#1565c0"
                    : "text.secondary",
                  fontSize: 13,
                  fontWeight: 700,
                  px: 1,
                  py: 0.45,
                  borderRadius: 1.5,
                  opacity: showAllDisabled ? 0.56 : 1,
                  cursor: showAllDisabled ? "not-allowed" : "pointer",
                  border: "1px solid",
                  borderColor: showAllActive
                    ? isDark
                      ? "rgba(125,211,252,0.45)"
                      : "rgba(21,101,192,0.28)"
                    : isDark
                      ? "rgba(148,163,184,0.22)"
                      : "rgba(15,23,42,0.1)",
                  bgcolor: showAllActive
                    ? isDark
                      ? "rgba(125,211,252,0.12)"
                      : "rgba(21,101,192,0.08)"
                    : isDark
                      ? "rgba(148,163,184,0.08)"
                      : "rgba(15,23,42,0.03)",
                  "&:hover": showAllDisabled
                    ? undefined
                    : {
                        bgcolor: showAllActive
                          ? isDark
                            ? "rgba(125,211,252,0.18)"
                            : "rgba(21,101,192,0.12)"
                          : "action.hover",
                      },
                }}
              >
                <Typography
                  variant="body2"
                  sx={{
                    color: "inherit",
                    fontSize: "inherit",
                    fontWeight: "inherit",
                  }}
                >
                  {showAllLabel}
                </Typography>
              </Box>
            ) : (
              <Box sx={{ minWidth: 12, minHeight: 1 }} />
            )}
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
        inputValue={inputValue}
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
          setStickyHiddenValues([]);
          resetHierarchyHover();
        }}
        onInputChange={(_, nextInputValue, reason) => {
          if (reason === "input") {
            setInputValue(nextInputValue);
            return;
          }
          if (reason === "clear") {
            setInputValue("");
            return;
          }
          setInputValue(selectedOption?.label || nextInputValue || "");
        }}
        filterOptions={(items, state) => {
          const query = state.inputValue.trim().toLowerCase();
          if (!query) return items;
          const selectedLabel = String(selectedOption?.label || "").trim().toLowerCase();
          const selectedOptionValue = String(selectedOption?.value || "").trim().toLowerCase();
          if (query === selectedLabel || query === selectedOptionValue) {
            return items;
          }
          return items.filter((option) =>
            [option.label, option.value, option.meta, option.project_name]
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
            sx={textFieldSx}
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
        renderOption={(props, option) => {
          const optionIsHidden = isOptionHidden(option);
          const { key, ...optionProps } = props;
          return (
            <Box
              component="li"
              key={key}
              {...optionProps}
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
                  opacity: optionIsHidden ? 0.58 : 1,
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
                    color: optionIsHidden ? "text.secondary" : "text.primary",
                    opacity: optionIsHidden ? 0.82 : 1,
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
                    color: optionIsHidden ? "text.secondary" : "success.main",
                    bgcolor: optionIsHidden ? "action.hover" : "rgba(46, 125, 50, 0.12)",
                    border: "1px solid",
                    borderColor: optionIsHidden ? "divider" : "rgba(46, 125, 50, 0.2)",
                    opacity: optionIsHidden ? 0.78 : 1,
                  }}
                >
                  {option.meta}
                </Box>
              ) : null}
            </Box>
          );
        }}
      />
      {open && showHierarchyMenu && activeProjectEntry && activeProjectRect ? (
        <Box sx={getSubmenuLayerSx(activeProjectRect, 340, theme.zIndex.modal + 2)}>
          {renderFlyoutPanel(
            (activeProjectEntry.items || []).map((option) =>
              renderMenuLeaf(option, { showPath: false })
            ),
            340,
            { pt: 0.15, pb: 0.75, px: 0.75 }
          )}
        </Box>
      ) : null}
    </Box>
  );
};

export default ChannelSwitcher;
