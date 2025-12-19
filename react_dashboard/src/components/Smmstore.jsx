import {
  Box,
  Button,
  Chip,
  FormControl,
  IconButton,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography,
} from "@mui/material";
import {
  DatePicker,
  LocalizationProvider,
  TimePicker,
} from "@mui/x-date-pickers";
import { AdapterDayjs } from "@mui/x-date-pickers/AdapterDayjs";
import { useTheme } from "@mui/material/styles";
import { useCallback, useContext, useEffect, useMemo, useState } from "react";
import { UserContext } from "../context/UserContext";
import { tokens } from "../theme";
import { API_BASE } from "../config";
import RefreshOutlinedIcon from "@mui/icons-material/RefreshOutlined";
import dayjs from "dayjs";

const ORDERS_STORAGE_KEY = "smmstore.orders";

const Smmstore = () => {
  const theme = useTheme();
  const colors = tokens(theme.palette.mode);
  const { user } = useContext(UserContext);

  const [balance, setBalance] = useState(null);
  const [balanceCurrency, setBalanceCurrency] = useState("");
  const [balanceError, setBalanceError] = useState("");
  const [loadingBalance, setLoadingBalance] = useState(false);

  const apiKey = user?.smmstore_api_key || "";
  const hasKey = useMemo(() => apiKey.trim().length > 0, [apiKey]);

  const cardSx = useMemo(
    () => ({
      p: 2.5,
      borderRadius: 2.5,
      border:
        theme.palette.mode === "dark"
          ? "1px solid rgba(148,163,184,0.25)"
          : `1px solid ${theme.palette.divider}`,
      bgcolor:
        theme.palette.mode === "dark"
          ? "rgba(17,24,39,0.85)"
          : "rgba(255,255,255,0.92)",
      boxShadow:
        theme.palette.mode === "dark"
          ? "0 10px 28px rgba(2,6,23,0.6)"
          : "0 10px 24px rgba(15,23,42,0.08)",
      transition: "transform 180ms ease, box-shadow 180ms ease",
      "&:hover": {
        transform: "translateY(-2px)",
        boxShadow:
          theme.palette.mode === "dark"
            ? "0 16px 32px rgba(2,6,23,0.7)"
            : "0 16px 30px rgba(15,23,42,0.12)",
      },
    }),
    [theme.palette.divider, theme.palette.mode]
  );

  const [servicesByCategory, setServicesByCategory] = useState({});
  const [category, setCategory] = useState("");
  const [service, setService] = useState("");
  const [serviceIdMap, setServiceIdMap] = useState({});
  const [search, setSearch] = useState("");
  const [showSuggestions, setShowSuggestions] = useState(false);

  const [link, setLink] = useState("");
  const [quantity, setQuantity] = useState("1000");

  const [runDate, setRunDate] = useState(() => dayjs());
  const [runTime, setRunTime] = useState(() => dayjs());

  const [dripFeed, setDripFeed] = useState(false);
  const [runs, setRuns] = useState("");
  const [interval, setInterval] = useState("");

  const [orders, setOrders] = useState([]);
  const [orderError, setOrderError] = useState("");
  const [loadingServices, setLoadingServices] = useState(false);

  const apiRequest = useCallback(
    async (endpoint, payload, signal) => {
      if (!hasKey) return { error: "Missing API key. Set it in Profile." };
      const token = localStorage.getItem("access_token");

      try {
        const resp = await fetch(`${API_BASE}${endpoint}`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify(payload || {}),
          signal,
        });
        const data = await resp.json();
        if (!resp.ok) {
          return { error: data?.detail || data?.error || "Request failed" };
        }
        return data;
      } catch (err) {
        if (err?.name === "AbortError") return { error: "aborted" };
        return { error: err?.message || "Request failed" };
      }
    },
    [hasKey]
  );

  const fetchBalance = useCallback(
    async (signal) => {
      if (!hasKey) return;
      setLoadingBalance(true);
      setBalanceError("");

      try {
      const data = await apiRequest("/api/smmstore/balance", {}, signal);
      if (data?.error === "aborted") return;
      if (data?.error) throw new Error(data.error);

        const value = data?.balance ?? null;
        setBalance(value !== null ? Number(value) : null);
        setBalanceCurrency(data?.currency || "");
      } catch (err) {
        if (err?.name === "AbortError") return;
        setBalance(null);
        setBalanceCurrency("");
        setBalanceError(err?.message || "Unable to load balance");
      } finally {
        setLoadingBalance(false);
      }
    },
    [apiRequest, hasKey]
  );

  useEffect(() => {
    const controller = new AbortController();
    fetchBalance(controller.signal);
    return () => controller.abort();
  }, [fetchBalance]);

  useEffect(() => {
    const controller = new AbortController();
    const loadServices = async () => {
      if (!hasKey) return;
      setLoadingServices(true);

      const data = await apiRequest(
        "/api/smmstore/services",
        {},
        controller.signal
      );
      if (data?.error || data === "aborted") {
        setLoadingServices(false);
        return;
      }

      const list = Array.isArray(data) ? data : data?.services || [];
      const grouped = {};
      const idMap = {};

      list.forEach((item) => {
        const cat = item?.category || "Unknown";
        grouped[cat] = grouped[cat] || [];
        grouped[cat].push(item);

        const label = `${item.service} - ${item.name}`;
        idMap[label] = item.service;
      });

      setServicesByCategory(grouped);
      setServiceIdMap(idMap);

      const firstCat = Object.keys(grouped)[0] || "";
      setCategory(firstCat);
      if (firstCat && grouped[firstCat]?.length) {
        const firstLabel = `${grouped[firstCat][0].service} - ${grouped[firstCat][0].name}`;
        setService(firstLabel);
      }

      setLoadingServices(false);
    };

    loadServices();
    return () => controller.abort();
  }, [apiRequest, hasKey]);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(ORDERS_STORAGE_KEY);
      setOrders(raw ? JSON.parse(raw) : []);
    } catch {
      setOrders([]);
    }
  }, []);

  useEffect(() => {
    try {
      localStorage.setItem(ORDERS_STORAGE_KEY, JSON.stringify(orders));
    } catch {
      // ignore storage errors
    }
  }, [orders]);

  const filteredServices = useMemo(() => {
    const keyword = search.trim().toLowerCase();
    if (!keyword) return [];
    const results = [];

    Object.values(servicesByCategory).forEach((items) => {
      items.forEach((item) => {
        const label = `${item.service} - ${item.name}`;
        if (
          String(item.service).toLowerCase().includes(keyword) ||
          item.name?.toLowerCase().includes(keyword)
        ) {
          results.push(label);
        }
      });
    });

    return results.slice(0, 100);
  }, [search, servicesByCategory]);

  const handleSelectService = useCallback((label) => {
    setService(label);
    setSearch(label);
    setShowSuggestions(false);
  }, []);

  const getStatusColor = useCallback((status) => {
    const label = String(status || "").toLowerCase();
    if (label.includes("completed")) return "success";
    if (label.includes("partial")) return "warning";
    if (label.includes("cancel") || label.includes("fail")) return "error";
    if (label.includes("queue") || label.includes("processing")) return "info";
    return "default";
  }, []);

  const buildRunAt = useCallback(() => {
    if (!runDate || !runTime) return new Date();
    const merged = runDate
      .hour(runTime.hour())
      .minute(runTime.minute())
      .second(0)
      .millisecond(0);
    return merged.toDate();
  }, [runDate, runTime]);

  const addOrderToQueue = useCallback((data) => {
    setOrders((prev) => [...prev, data]);
  }, []);

  const updateOrder = useCallback((id, changes) => {
    setOrders((prev) =>
      prev.map((order) => (order.id === id ? { ...order, ...changes } : order))
    );
  }, []);

  const sendOrder = useCallback(
    async (order) => {
      const params = {
        action: "add",
        service: order.serviceId,
        link: order.link,
        quantity: order.quantity,
      };
      if (order.dripFeed) {
        params.runs = order.runs;
        params.interval = order.interval;
      }
      const resp = await apiRequest("/api/smmstore/order", params);
      if (resp?.error) {
        updateOrder(order.id, { status: "Failed" });
        return;
      }
      const orderId = String(resp?.order || "").trim();
      if (!orderId) {
        updateOrder(order.id, { status: "Failed" });
        return;
      }
      updateOrder(order.id, { orderId, status: "In Queue" });
    },
    [apiRequest, updateOrder]
  );

  const submitOrder = useCallback(() => {
    setOrderError("");
    if (!hasKey) return setOrderError("Missing API key. Set it in Profile.");
    if (!service) return setOrderError("Please select a service.");
    if (!link.trim()) return setOrderError("Please enter a link.");
    if (!quantity || Number(quantity) <= 0)
      return setOrderError("Quantity must be greater than 0.");

    const runAt = buildRunAt();
    const now = new Date();
    const orderId = `ord_${Date.now()}`;

    const newOrder = {
      id: orderId,
      runAt: runAt.toISOString(),
      service,
      serviceId: serviceIdMap[service] || service.split(" - ")[0]?.trim(),
      link: link.trim(),
      quantity: String(quantity),
      status: "In Queue",
      orderId: "",
      charge: "",
      remains: "",
      dripFeed,
      runs: dripFeed ? String(runs || "") : "",
      interval: dripFeed ? String(interval || "") : "",
    };

    addOrderToQueue(newOrder);

    if (runAt <= now) {
      sendOrder(newOrder);
    }
  }, [
    addOrderToQueue,
    buildRunAt,
    dripFeed,
    hasKey,
    interval,
    link,
    quantity,
    runs,
    sendOrder,
    service,
    serviceIdMap,
  ]);

  useEffect(() => {
    const timer = setInterval(() => {
      const now = Date.now();
      orders.forEach((order) => {
        if (order.orderId || order.status !== "In Queue") return;
        if (new Date(order.runAt).getTime() <= now) {
          sendOrder(order);
        }
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [orders, sendOrder]);

  useEffect(() => {
    const poll = setInterval(() => {
      orders.forEach(async (order) => {
        if (!order.orderId) return;
        const statusLower = (order.status || "").toLowerCase();
        if (
          statusLower.includes("completed") ||
          statusLower.includes("partial") ||
          statusLower.includes("cancel")
        ) {
          return;
        }
        const resp = await apiRequest("/api/smmstore/status", {
          order: order.orderId,
        });
        if (resp?.error) return;
        updateOrder(order.id, {
          status: resp.status || "Unknown",
          charge: resp.charge || "",
          remains: resp.remains || resp.remain || "",
        });
      });
    }, 15000);
    return () => clearInterval(poll);
  }, [apiRequest, orders, updateOrder]);

  return (
    <Stack spacing={2.5}>
      {/* Header (left) + Balance (right) */}
      <Stack
        direction="row"
        justifyContent="space-between"
        alignItems="flex-start"
        gap={2}
        flexWrap="wrap"
      >
        <Box>
          {!hasKey && (
            <Typography variant="body2" color="text.secondary" sx={{ mt: 0.75 }}>
              Set your API key in Profile to load balance.
            </Typography>
          )}
          {hasKey && balanceError && (
            <Typography variant="body2" color="error" sx={{ mt: 0.75 }}>
              {balanceError}
            </Typography>
          )}
        </Box>

        <Stack direction="row" alignItems="center" spacing={1.5}>
          <Box textAlign="right">

            <Typography
              variant="h4"
              fontWeight="800"
              color={colors.greenAccent[400]}
              lineHeight={1.1}
            >
              {loadingBalance
                ? "..."
                : balance !== null
                ? `${balance.toLocaleString()} ${balanceCurrency}`
                : "--"}
            </Typography>
          </Box>

          <IconButton
            size="small"
            onClick={() => fetchBalance()}
            disabled={!hasKey || loadingBalance}
            aria-label="Refresh balance"
          >
            <RefreshOutlinedIcon fontSize="small" />
          </IconButton>
        </Stack>
      </Stack>

      {/* Form */}
      <Paper elevation={0} sx={cardSx}>
        <Stack spacing={2}>
          {/* Service Selection */}
          <Stack spacing={1}>
            <Typography variant="subtitle1" fontWeight="700">
              Service Selection
            </Typography>

            {/* Search + Category + Service (same row, responsive) */}
            <Stack
              direction={{ xs: "column", md: "row" }}
              spacing={2}
              alignItems="flex-start"
            >
              {/* Search */}
              <Box
                sx={{
                  flex: 1.4,
                  minWidth: { xs: "100%", md: 320 },
                  position: "relative",
                }}
              >
                <TextField
                  label="Search Service"
                  value={search}
                  onChange={(e) => {
                    setSearch(e.target.value);
                    setShowSuggestions(true);
                  }}
                  onFocus={() => setShowSuggestions(true)}
                  onBlur={() => {
                    // delay để click được suggestion
                    setTimeout(() => setShowSuggestions(false), 150);
                  }}
                  fullWidth
                  size="small"
                  sx={{
                    "& .MuiOutlinedInput-root": {
                      transition: "box-shadow 160ms ease",
                      "&:hover": {
                        boxShadow:
                          theme.palette.mode === "dark"
                            ? "0 0 0 2px rgba(96,165,250,0.25)"
                            : "0 0 0 2px rgba(56,189,248,0.18)",
                      },
                      "&.Mui-focused": {
                        boxShadow:
                          theme.palette.mode === "dark"
                            ? "0 0 0 2px rgba(96,165,250,0.45)"
                            : "0 0 0 2px rgba(56,189,248,0.35)",
                      },
                    },
                  }}
                />

                {showSuggestions && search && filteredServices.length > 0 && (
                  <Paper
                    variant="outlined"
                    sx={{
                      position: "absolute",
                      top: "calc(100% + 6px)",
                      left: 0,
                      right: 0,
                      zIndex: 20,
                      maxHeight: 260,
                      overflow: "auto",
                      borderRadius: 2,
                      borderColor: theme.palette.divider,
                    }}
                    onMouseDown={(e) => e.preventDefault()}
                  >
                    {filteredServices.map((item) => (
                      <Box
                        key={item}
                        sx={{
                          px: 1.5,
                          py: 1,
                          cursor: "pointer",
                          bgcolor:
                            item === service ? "action.selected" : "transparent",
                          transition:
                            "background-color 160ms ease, transform 160ms ease",
                          "&:hover": {
                            bgcolor: "action.hover",
                            transform: "translateX(2px)",
                          },
                        }}
                        onClick={() => handleSelectService(item)}
                      >
                        <Typography variant="body2">{item}</Typography>
                      </Box>
                    ))}
                  </Paper>
                )}
              </Box>

              {/* Category */}
              <FormControl
                size="small"
                sx={{ flex: 0.8, minWidth: { xs: "100%", md: 200 } }}
              >
                <InputLabel>Category</InputLabel>
                <Select
                  value={category}
                  label="Category"
                  onChange={(e) => {
                    const next = e.target.value;
                    setCategory(next);
                    const items = servicesByCategory[next] || [];
                    if (items.length) {
                      const label = `${items[0].service} - ${items[0].name}`;
                      setService(label);
                    }
                  }}
                >
                  {Object.keys(servicesByCategory).map((cat) => (
                    <MenuItem key={cat} value={cat}>
                      {cat}
                    </MenuItem>
                  ))}
                </Select>
              </FormControl>

              {/* Service */}
              <FormControl
                size="small"
                sx={{ flex: 1.2, minWidth: { xs: "100%", md: 320 } }}
              >
                <InputLabel>Service</InputLabel>
                <Select
                  value={service}
                  label="Service"
                  onChange={(e) => setService(e.target.value)}
                >
                  {(servicesByCategory[category] || []).map((item) => {
                    const label = `${item.service} - ${item.name}`;
                    return (
                      <MenuItem key={label} value={label}>
                        {label}
                      </MenuItem>
                    );
                  })}
                </Select>
              </FormControl>
            </Stack>
          </Stack>

          {/* Schedule */}
          <Stack spacing={1}>
            <Typography variant="subtitle1" fontWeight="700">
              Schedule
            </Typography>
            <LocalizationProvider dateAdapter={AdapterDayjs}>
              <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
                <DatePicker
                  label="Run Date"
                  value={runDate}
                  onChange={(value) => setRunDate(value)}
                  slotProps={{
                    textField: {
                      size: "small",
                      sx: { minWidth: 240, flex: 1 },
                    },
                  }}
                />
                <TimePicker
                  label="Time"
                  value={runTime}
                  onChange={(value) => setRunTime(value)}
                  ampm={false}
                  slotProps={{
                    textField: {
                      size: "small",
                      sx: { minWidth: 200, flex: 1 },
                    },
                  }}
                />
              </Stack>
            </LocalizationProvider>
          </Stack>

          {/* Order Details (gọn hơn: Link + Quantity cùng hàng) */}
          <Stack spacing={1}>
            <Typography variant="subtitle1" fontWeight="700">
              Order Details
            </Typography>
            <Stack direction={{ xs: "column", sm: "row" }} spacing={2}>
              <TextField
                label="Link"
                value={link}
                onChange={(e) => setLink(e.target.value)}
                fullWidth
                size="small"
              />
              <TextField
                label="Quantity"
                value={quantity}
                onChange={(e) => setQuantity(e.target.value)}
                size="small"
                sx={{ width: { xs: "100%", sm: 200 } }}
              />
            </Stack>
          </Stack>

          {/* Drip feed + Submit */}
          <Stack
            direction="row"
            spacing={2}
            alignItems="center"
            flexWrap="wrap"
            justifyContent="space-between"
          >
            <Stack direction="row" spacing={2} alignItems="center" flexWrap="wrap">
              <Button
                variant={dripFeed ? "contained" : "outlined"}
                color={dripFeed ? "success" : "error"}
                onClick={() => setDripFeed((prev) => !prev)}
                size="small"
                sx={{
                  transition: "transform 160ms ease, box-shadow 160ms ease",
                  "&:hover": {
                    transform: "translateY(-1px)",
                    boxShadow:
                      theme.palette.mode === "dark"
                        ? "0 6px 16px rgba(2,6,23,0.35)"
                        : "0 6px 16px rgba(15,23,42,0.15)",
                  },
                }}
              >
                Drip-Feed {dripFeed ? "On" : "Off"}
              </Button>
              {dripFeed && (
                <>
                  <TextField
                    label="Runs"
                    value={runs}
                    onChange={(e) => setRuns(e.target.value)}
                    size="small"
                    sx={{ width: 140 }}
                  />
                  <TextField
                    label="Interval (min)"
                    value={interval}
                    onChange={(e) => setInterval(e.target.value)}
                    size="small"
                    sx={{ width: 180 }}
                  />
                </>
              )}
            </Stack>
            <Button
              variant="contained"
              color="secondary"
              onClick={submitOrder}
              disabled={!hasKey || loadingServices}
              sx={{
                width: 180,
                ml: "auto",
                transition: "transform 160ms ease, box-shadow 160ms ease",
                "&:hover": {
                  transform: "translateY(-1px)",
                  boxShadow:
                    theme.palette.mode === "dark"
                      ? "0 8px 18px rgba(2,6,23,0.35)"
                      : "0 8px 18px rgba(15,23,42,0.18)",
                },
              }}
            >
              Submit
            </Button>
          </Stack>

          {orderError && (
            <Typography variant="body2" color="error">
              {orderError}
            </Typography>
          )}

        </Stack>
      </Paper>

      {/* Table */}
      <Paper
        elevation={0}
        sx={{
          borderRadius: 2.5,
          border:
            theme.palette.mode === "dark"
              ? "1px solid rgba(148,163,184,0.25)"
              : `1px solid ${theme.palette.divider}`,
          overflow: "hidden",
          bgcolor:
            theme.palette.mode === "dark"
              ? "rgba(15,23,42,0.65)"
              : "transparent",
          transition: "transform 180ms ease, box-shadow 180ms ease",
          "&:hover": {
            transform: "translateY(-2px)",
            boxShadow:
              theme.palette.mode === "dark"
                ? "0 16px 32px rgba(2,6,23,0.6)"
                : "0 16px 28px rgba(15,23,42,0.12)",
          },
        }}
      >
        <TableContainer>
          <Table size="small">
            <TableHead>
              <TableRow
                sx={{
                  bgcolor:
                    theme.palette.mode === "dark"
                      ? "rgba(30,41,59,0.7)"
                      : "action.hover",
                }}
              >
                <TableCell>Run Time</TableCell>
                <TableCell>Order ID</TableCell>
                <TableCell>Service</TableCell>
                <TableCell>Link</TableCell>
                <TableCell>Quantity</TableCell>
                <TableCell>Status</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {orders.map((order, index) => (
                <TableRow
                  key={order.id}
                  sx={{
                    bgcolor: index % 2 === 0 ? "transparent" : "action.hover",
                    transition: "background-color 160ms ease",
                    "&:hover": {
                      bgcolor:
                        theme.palette.mode === "dark"
                          ? "rgba(30,41,59,0.6)"
                          : "rgba(148,163,184,0.2)",
                    },
                  }}
                >
                  <TableCell>
                    {order.runAt ? new Date(order.runAt).toLocaleString() : ""}
                  </TableCell>
                  <TableCell>{order.orderId}</TableCell>
                  <TableCell>{order.serviceId}</TableCell>
                  <TableCell>
                    <a
                      href={order.link}
                      target="_blank"
                      rel="noreferrer"
                      style={{ color: colors.blueAccent[400] }}
                    >
                      {order.link}
                    </a>
                  </TableCell>
                  <TableCell>{order.quantity}</TableCell>
                  <TableCell>
                    <Chip
                      label={order.status || "Unknown"}
                      size="small"
                      color={getStatusColor(order.status)}
                      variant={order.status ? "filled" : "outlined"}
                    />
                  </TableCell>
                </TableRow>
              ))}
              {orders.length === 0 && (
                <TableRow>
                  <TableCell colSpan={6}>
                    <Typography variant="body2" color="text.secondary">
                      No orders yet.
                    </Typography>
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </Paper>

      <Stack direction="row" spacing={2} flexWrap="wrap" />
    </Stack>
  );
};

export default Smmstore;
